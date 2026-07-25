#!/usr/bin/env bash
# Downloads the oasdiff binary into tools/. Run once per checkout.
# Alternative if you prefer not to vendor a binary:
#   docker run --rm -v "$PWD:/specs" tufin/oasdiff breaking /specs/base.json /specs/revision.json
# The Docker route is avoided here because MSYS mangles Windows volume paths.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$ROOT/tools"
cd "$ROOT/tools"

if [ -x "./oasdiff.exe" ] || [ -x "./oasdiff" ]; then
  echo "oasdiff already present"
  exit 0
fi

gh release download --repo oasdiff/oasdiff --pattern '*windows_amd64.tar.gz' --clobber
tar -xzf ./*windows_amd64.tar.gz
rm -f ./*windows_amd64.tar.gz
./oasdiff.exe --version
