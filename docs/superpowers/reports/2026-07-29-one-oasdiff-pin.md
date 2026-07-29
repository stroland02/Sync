# One place names the oasdiff release, and both installers read it

**Date:** 2026-07-29
**Closes:** the follow-up named in `docs/superpowers/reports/2026-07-29-oasdiff-version-settled.md` §8.

That report measured eleven working copies of this repository on one machine holding two different
oasdiff builds under one path, and traced it to two mechanisms that disagreed by construction:
`.github/workflows/ci.yml` pinned a version, and `scripts/bootstrap_tools.sh` downloaded whatever
release was latest on the day a checkout ran it. This is the reconciliation. It changes no
measurement — §5 of that report re-ran the generated-vendor corpus on both builds and found the
artifacts identical field by field — so what follows is a correctness-of-process change and nothing
else.

## 1. Where the pin lives

`.oasdiff-version` at the repository root, holding `1.26.1`, which is the version CI has been
running all along. Comment lines and blank lines are skipped, so the file carries the argument for
its own existence next to the value.

Both installers read that file and neither names a version of its own:

| reader | how |
|---|---|
| `scripts/bootstrap_tools.sh` | `grep -m1 -Ev '^[[:space:]]*(#\|$)' "$PIN"`, then every space stripped |
| `.github/workflows/ci.yml`, `Install oasdiff` | the same expression, against `.oasdiff-version` |

The space-stripping earns its place, but not for the reason it was written for. It went in against
`core.autocrlf=true`, which leaves a CR at the end of every line of a Windows working tree. Measured:
**Windows `grep` drops that CR by itself**, so the CRLF case never reaches the scrub. What does reach
it is a trailing space after the version, which `grep` returns intact and which builds a tag no
release answers to. Both shapes are covered by the tests; only the second can fail.

**What was rejected.**

- **The workflow's `env` block stays authoritative and the script reads it.** Rejected on two
  counts. It makes a shell script parse YAML, which means either a fragile `grep` against a file
  whose shape is nobody's contract, or a YAML dependency in a script whose whole job is to run
  before dependencies exist. And it points a local developer's toolchain at a CI file, so a change
  to how CI is laid out breaks bootstrapping on a machine that never runs CI.
- **`pyproject.toml`.** Python parses it for free, but `bootstrap_tools.sh` is bash and would need
  a TOML parser to read one string. The deeper objection is that the field is not a Python
  dependency and does not belong in a dependency manifest; `uv` would neither install it nor check
  it, so the file would carry a value it has no opinion about.
- **Keeping `OASDIFF_VERSION: 1.26.1` in the workflow and adding a test that it equals the pin
  file.** This was the tempting one, because it leaves CI readable at a glance. It was rejected
  because a test asserting two files agree is a worse mechanism than one file: it converts a
  structural guarantee into a check somebody can delete, and it leaves a second version literal in
  the tree for a future reader to edit. The workflow now derives the version and holds no literal,
  which is why the agreement test in this task is behavioural — it runs the workflow's own install
  step against a pin file naming `9.9.9` and asks which release the step went for.

## 2. A checkout already holding the wrong build

**It is refused, loudly, and nothing on disk is touched.** Chosen over replacing it.

The early exit this replaces checked *presence* — `if [ -x "./oasdiff.exe" ]` — which is exactly why
the spread never converged. A checkout that already had a binary was never upgraded, and a binary
copied from a sibling worktree was never looked at.

Replacing would converge the spread automatically, and it was the more attractive option until the
cost was named. `tools/` is gitignored and carries no history, so an overwrite is unrecoverable, and
the bytes it would overwrite are load-bearing evidence: §4 of the version report establishes which
binary produced each committed measurement by the fact that *the authoring checkouts still hold it,
unchanged*. A script that silently upgrades destroys the only artifact that argument rests on, and
it destroys it during a routine setup step nobody is watching.

The refusal names both versions, the sha256 of what is installed — the version string does not
identify the binary, which is the whole finding of §1 of that report — and the two commands that
replace it deliberately. The manual step it costs is one `rm`.

Run for real in this worktree, which holds 1.26.0 against a 1.26.1 pin:

```
bootstrap: this checkout holds an oasdiff the pin does not name.
  pinned:    oasdiff version 1.26.1   (/c/Users/strol/orca/workspaces/Sync/m2-parsing/.oasdiff-version)
  installed: oasdiff version 1.26.0
  sha256:    1e78ddce7d4477ee0a86718aa68ec7038357d1940fb053823238670f5ef472c8

Nothing was changed. tools/ is gitignored and has no history, so this is the only
copy of bytes a recorded measurement may have run on. Delete it yourself once you
know no committed artifact depends on this build:
  rm .../tools/oasdiff.exe && .../scripts/bootstrap_tools.sh
```

Exit code 1. The binary's sha256 and mtime were identical before and after.

A binary that exists and cannot run is a third case rather than "absent", and says so. Reading
`--version` without its exit code is the defect §7 of the version report found in the measurement
script, and it reappears here in a different costume: an unrunnable binary reports an empty version,
which reads as a version mismatch and sends the operator looking for a problem that is not there.

`scripts/measure_generated_vendor_noise.py` and `src/sync/signals/oasdiff.py` both resolve
`tools/oasdiff.exe` themselves and were deliberately not touched — they are owned by other tasks,
and neither needs to know about the pin to keep working. Nothing in the reconciliation required
reaching into `src/`.

## 3. What CI asserts

The install step ended with `tools/oasdiff --version`, which prints. It now compares:

```bash
installed="$(tools/oasdiff --version)"
if [ "$installed" != "oasdiff version ${version}" ]; then
  echo "pinned v${version} in .oasdiff-version, installed '${installed}'" >&2
  exit 1
fi
```

Equality against the full string rather than a substring, because `1.26` is a substring of both
builds this project has ever held and a check that matches both is not a check.

`scripts/bootstrap_tools.sh` gained the same assertion after extraction, for the same reason: a tag
and the bytes published under it can disagree, and printing a version does not notice. What that run
downloaded is that run's to remove, so a mismatch there deletes the binary — unlike anything the
script *found* already in place, which it never touches.

## 4. How the tests are known to be able to fail

Both installers are run for real, in Git Bash, which is the shell `CLAUDE.md` commits to. Only the
download is stubbed: `gh` and `curl` are replaced on `PATH` and no test reaches GitHub.

Two things about that harness are worth recording because both were found by watching a test that
should have failed pass instead:

- **`bash.exe` prepends its own `/mingw64/bin` and `/usr/bin` to whatever PATH it inherits.** A stub
  directory exported from Python lands *behind* the real `curl`, so the first version of these tests
  reached GitHub and came back with a 404 while asserting on a stub that never ran. The PATH has to
  be set by a shell that is already running.
- **The mutation driver read colourised pytest output** and matched none of it, so its first run
  reported all fourteen mutations surviving. A driver that reports nothing has to be
  distinguishable from a driver that found nothing; it now fails unless the run collected the
  expected number of tests.

The mutation table. Each row is one edit to a shipped file, with the suite run against it and then
reverted. Parametrised cases are `[lf]`, `[crlf]` and `[trailing-space]` on the pin's shape:

| # | mutation | tests killed |
|---|---|---|
| M1 | workflow hardcodes the version instead of reading the pin | `the_workflow_fetches_the_release_the_pin_names` ×3, `neither_installer_names_a_version_of_its_own[workflow]` |
| M2 | workflow prints the installed version instead of asserting it | `the_workflow_fails_when_it_installs_a_build_the_pin_does_not_name` |
| M3 | workflow reader takes line 1 instead of skipping comments | `the_workflow_fetches_the_release_the_pin_names` ×3 |
| M4 | bootstrap restores the presence-only early exit | `a_checkout_holding_an_unpinned_build_is_refused_and_left_untouched`, `a_binary_that_cannot_run_is_refused_rather_than_treated_as_absent` |
| M5 | bootstrap drops the tag from the download | `the_bootstrap_downloads_the_release_the_pin_names` ×3 |
| M6 | bootstrap replaces a wrong build instead of refusing | `a_checkout_holding_an_unpinned_build_is_refused_and_left_untouched` |
| M7 | bootstrap drops the post-download verification | `the_bootstrap_downloads_the_release_the_pin_names` ×3, `the_bootstrap_refuses_a_download_that_is_not_the_release_it_asked_for` |
| M8 | the presence check swallows the binary's exit code | `a_binary_that_cannot_run_is_refused_rather_than_treated_as_absent` |
| M9 | bootstrap drops `errexit` | **survived — see below** |
| M10 | bootstrap drops `errexit` *and* the post-download verification | `the_bootstrap_fails_when_the_download_fails`, `the_bootstrap_fails_when_the_download_produces_nothing`, `the_bootstrap_refuses_a_download_that_is_not_the_release_it_asked_for` |
| M11 | bootstrap reader takes line 1 instead of skipping comments | `the_bootstrap_downloads_the_release_the_pin_names` ×3, `a_checkout_holding_an_unpinned_build_is_refused_and_left_untouched`, `a_checkout_holding_the_pinned_build_succeeds_without_downloading` |
| M12 | bootstrap always downloads, even when the pinned build is present | `a_checkout_holding_the_pinned_build_succeeds_without_downloading` |
| M13 | the pin names two versions | `the_pin_names_exactly_one_version` |
| M14 | bootstrap names a version in a comment | `neither_installer_names_a_version_of_its_own[bootstrap]` |
| M15 | workflow does not scrub the pin's whitespace | `the_workflow_fetches_the_release_the_pin_names[trailing-space]` |
| M16 | bootstrap does not scrub the pin's whitespace | `the_bootstrap_downloads_the_release_the_pin_names[trailing-space]` |

**M8 survived the first time it was run, and the test was at fault.** With the exit code swallowed,
an unrunnable binary is refused anyway — as a version mismatch against an empty string — so the
assertion on the return code held. What the mutation destroyed was the diagnostic, and the test did
not look at it. It now asserts the message names `'--version' failed`, and M8 dies.

**A seventeenth mutation deleted code instead of killing a test, and that is the most useful thing
in this table.** The script had a helper normalising CR out of `--version` before comparing, on the
theory that a Windows console program may terminate with CRLF, and a test with a CRLF-emitting stub
that passed. Removing the normalisation killed nothing. The reason is that **the MSYS pipe
translates CRLF to LF on the way out of a subprocess**, so the CR never existed: measured on a stub
`printf`ing `\r\n`, and separately on the real `oasdiff.exe`, whose `--version` is LF-terminated on
both builds. The normalisation guarded a condition that cannot occur here and the test that
"covered" it could not fail. Both were deleted and the helper inlined at its two call sites. M15 and
M16 are the replacements: they target the same scrub in the *pin reader*, where the reachable input
is a trailing space rather than a CR.

**M9 survives, and the mutation is at fault rather than the test.** Dropping `errexit` alone does not
let a failed download through: `gh` fails, `tar` finds no archive and fails, and the post-download
verification then finds no binary and refuses. Two independent mechanisms cover that path, so
removing either one on its own changes nothing observable. M10 removes both and three tests die,
which is the evidence that the property is held rather than assumed. This is the same shape as the
two earlier occasions on this project where a surviving mutation turned out to be a bad mutation.

## 5. The real runs

No test downloads a binary. Two runs were taken by hand.

**The refusal**, in this worktree, is quoted in §2. Exit 1, sha256 and mtime unchanged.

**The download**, into a scratch checkout under `.cache/` holding only the script and the pin:

```
$ bash scripts/bootstrap_tools.sh
oasdiff version 1.26.1
$ sha256sum tools/oasdiff.exe
629d435b31a92658da366582da5d9eefc7191cb2761777b9800be1eb77636b9f
$ bash scripts/bootstrap_tools.sh
oasdiff version 1.26.1 already present
```

17,547,264 bytes. Both the hash and the byte count match the 1.26.1 row of §1 of the version report
exactly, which is the check that the pinned tag serves the same bytes that report identified. The
scratch checkout was deleted afterwards; no worktree's `tools/` was written to.

## 6. What this does not do

**It does not converge the eleven checkouts.** Refusing makes the divergence loud on the next
bootstrap in each of them; it does not fix it, by design. Seven working copies still hold 1.26.0 and
will now say so instead of exiting 0.

**Two of them should probably be left alone.** `m2-parsing` and `m2-symbols` authored the three
committed reports whose instrument §4 of the version report identifies *by the fact that those
checkouts still hold the binary*. Deleting those two binaries does not invalidate the reports — both
builds are now recorded by hash in `docs/superpowers/reports/recorded/` — but it does retire the
independent confirmation, and there is no reason to spend it.

**It does not move the pin.** 1.26.1 is what CI has been running. §5 of the version report covers
only the four generated vendors; the Stripe corpus is not covered, and the same report measured a
single run there producing 374,858 records against a documented range topping out at 215,126. A bump
needs that measurement, not this mechanism.

**It does not touch the idempotence exemption.** `CLAUDE.md` grants oasdiff-derived `vendor_change`
rows their exemption on the grounds that the differ returns a different answer every run *on both
pinned versions*. Pinning one version does not retire that; the instability is within a version, not
between two.
