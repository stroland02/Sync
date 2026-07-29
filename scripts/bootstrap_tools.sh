#!/usr/bin/env bash
# Downloads the pinned oasdiff release into tools/. Run once per checkout.
# Alternative if you prefer not to vendor a binary:
#   docker run --rm -v "$PWD:/specs" tufin/oasdiff breaking /specs/base.json /specs/revision.json
# The Docker route is avoided here because MSYS mangles Windows volume paths.
#
# A checkout already holding a different build is refused, never upgraded in place. tools/ is
# gitignored and carries no history, so an overwrite is the only copy of the bytes a recorded
# measurement ran on -- and those bytes are what
# docs/superpowers/reports/2026-07-29-oasdiff-version-settled.md is built out of.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIN="$ROOT/.oasdiff-version"

# First line that is neither blank nor a comment, with every space stripped. Windows grep
# already drops the CR that core.autocrlf leaves on every line here; what it does not drop is
# a trailing space somebody left after the version, which builds a tag no release answers to.
WANT="$(grep -m1 -Ev '^[[:space:]]*(#|$)' "$PIN")"
WANT="${WANT//[[:space:]]/}"
if [ -z "$WANT" ]; then
  echo "bootstrap: $PIN names no version" >&2
  exit 1
fi
EXPECT="oasdiff version $WANT"

mkdir -p "$ROOT/tools"
cd "$ROOT/tools"

for exe in ./oasdiff.exe ./oasdiff; do
  [ -x "$exe" ] || continue

  # A binary that exists and cannot run is a third case, not "absent". Reading --version
  # without its exit code writes an empty version into whatever asked, which is the defect
  # 2026-07-29-oasdiff-version-settled.md §7 found in the measurement script.
  if ! HAVE="$("$exe" --version)"; then
    echo "bootstrap: $ROOT/tools/${exe#./} is present and '--version' failed" >&2
    exit 1
  fi
  if [ "$HAVE" = "$EXPECT" ]; then
    echo "$HAVE already present"
    exit 0
  fi

  # The version string does not identify the binary -- two builds answer to the same name --
  # so the refusal quotes the hash a recorded artifact can be matched against.
  SUM="unavailable"
  if command -v sha256sum >/dev/null 2>&1; then
    SUM="$(sha256sum "$exe" | cut -d' ' -f1)"
  fi
  {
    echo "bootstrap: this checkout holds an oasdiff the pin does not name."
    echo "  pinned:    $EXPECT   ($PIN)"
    echo "  installed: $HAVE"
    echo "  sha256:    $SUM"
    echo
    echo "Nothing was changed. tools/ is gitignored and has no history, so this is the only"
    echo "copy of bytes a recorded measurement may have run on. Delete it yourself once you"
    echo "know no committed artifact depends on this build:"
    echo "  rm $ROOT/tools/${exe#./} && $ROOT/scripts/bootstrap_tools.sh"
  } >&2
  exit 1
done

gh release download "v$WANT" --repo oasdiff/oasdiff --pattern '*windows_amd64.tar.gz' --clobber
tar -xzf ./*windows_amd64.tar.gz
rm -f ./*windows_amd64.tar.gz

# A tag and the bytes published under it can disagree. What this run downloaded is this run's
# to remove, unlike anything it found already here.
if ! GOT="$(./oasdiff.exe --version)" || [ "$GOT" != "$EXPECT" ]; then
  rm -f ./oasdiff.exe
  echo "bootstrap: asked for v$WANT and got '${GOT-}'; removed it" >&2
  exit 1
fi
echo "$GOT"
