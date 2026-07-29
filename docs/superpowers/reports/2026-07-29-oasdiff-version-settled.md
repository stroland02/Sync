# Which oasdiff produced these numbers?

**Date:** 2026-07-29
**Settles:** the discrepancy between `2026-07-29-oasdiff-determinism.md` §1,
`2026-07-29-oasdiff-convergence.md`, `2026-07-29-generated-vendor-noise.md` §2 — all three of which
say their measurements were taken on oasdiff 1.26.0 — and the binary a reader finds under `tools/`
today, which reports 1.26.1.

**Both are true, neither report was wrong, and nothing was replaced.** There is no such file as
*the* oasdiff binary in this project. `tools/` is gitignored and populated per checkout, and
`scripts/bootstrap_tools.sh` pins no version, so eleven working copies of this repository on this
machine hold **two different builds at the same time** — seven on 1.26.0, four on 1.26.1, all under
the same path, all answering to the same name. The three reports were written in checkouts holding
1.26.0, and those checkouts still hold 1.26.0 today. The brief that raised the discrepancy read the
binary in a checkout holding 1.26.1. Both readings were correct about different files.

The version question is settled and it changes nothing about what the reports concluded: **72 runs
of the generated-vendor measurement on 1.26.1 reproduce every number in that report exactly**, and
the Stripe instability reproduces on 1.26.1 as the determinism report already recorded.

## 1. What is installed

Every checkout of this repository on this machine, on 2026-07-29:

| checkout | version | sha256 (16) | bytes | exe mtime | `LICENSE` |
|---|---|---|---:|---|---|
| `orca/Sync/Sync` (main) | 1.26.1 | `629d435b31a92658` | 17,547,264 | 2026-07-27 06:57:27 | yes |
| `workspaces/Sync/m1-forge` | 1.26.1 | `629d435b31a92658` | 17,547,264 | 2026-07-27 06:57:27 | yes |
| `workspaces/Sync/m1-nodes` | 1.26.1 | `629d435b31a92658` | 17,547,264 | 2026-07-27 06:57:27 | yes |
| `workspaces/Sync/m1-store` | 1.26.1 | `629d435b31a92658` | 17,547,264 | 2026-07-27 17:43:15 | no |
| `workspaces/Sync/m1-static-gate` | 1.26.0 | `1e78ddce7d4477ee` | 17,546,240 | 2026-07-28 04:21:24 | no |
| `workspaces/Sync/m2-depth` | 1.26.0 | `1e78ddce7d4477ee` | 17,546,240 | 2026-07-28 04:50:19 | no |
| `workspaces/Sync/m2-parsing` | 1.26.0 | `1e78ddce7d4477ee` | 17,546,240 | 2026-07-28 04:37:45 | no |
| `workspaces/Sync/m2-symbols` | 1.26.0 | `1e78ddce7d4477ee` | 17,546,240 | 2026-07-28 04:37:46 | no |
| `.claude/worktrees/sync-m0-vendor-change` | 1.26.0 | `1e78ddce7d4477ee` | 17,546,240 | 2026-07-24 07:42:07 | yes |
| `.claude/worktrees/sync-solo-a` | 1.26.0 | `1e78ddce7d4477ee` | 17,546,240 | 2026-07-28 23:18:38 | yes |
| `.claude/worktrees/sync-solo-b` | 1.26.0 | `1e78ddce7d4477ee` | 17,546,240 | 2026-07-29 01:10:35 | yes |

Exactly two distinct files:

| sha256 | bytes | reports |
|---|---:|---|
| `1e78ddce7d4477ee0a86718aa68ec7038357d1940fb053823238670f5ef472c8` | 17,546,240 | `oasdiff version 1.26.0` |
| `629d435b31a92658da366582da5d9eefc7191cb2761777b9800be1eb77636b9f` | 17,547,264 | `oasdiff version 1.26.1` |

## 2. What dates it, and what that does not establish

The exe's own mtime dates the **upstream release build**, not the local install. `bootstrap_tools.sh`
extracts with `tar -xzf`, which preserves the archive's internal timestamps, so the mtime that
arrives is the one the release was built with:

| file | exe mtime (UTC) | release | published (UTC) | difference |
|---|---|---|---|---:|
| `sync-m0-vendor-change/tools/oasdiff.exe` | 2026-07-24 11:42:07 | v1.26.0 | 2026-07-24 11:42:23 | 16 s before |
| `Sync/Sync/tools/oasdiff.exe` | 2026-07-27 10:57:27 | v1.26.1 | 2026-07-27 10:57:37 | 10 s before |

Build, then publish, seconds apart. That is a strong date on **which release the bytes are** —
independent of the `--version` string, which is the thing under question — and it is a second,
independent confirmation that the two files are v1.26.0 and v1.26.1 rather than two builds of one.

Copies made by hand carry the copy time instead, with sub-second precision the tarball's whole-second
timestamps never have. That is what distinguishes rows 4–8 and 10–11 of the table above from a fresh
extraction, and it is why four of the 1.26.0 checkouts carry no `LICENSE`: only the exe was copied.

**What none of it establishes is when any of this was installed here**, which is what would actually
date the measurements. The `tools/` directory mtime is the closest thing — `Sync/Sync/tools` is
2026-07-27 17:42:33, consistent with `bootstrap_tools.sh` deleting the tarball after extraction —
but a directory mtime moves on any later add or remove, so it is an upper bound and not a record.

**Nothing on disk records an intended version at all.** There is no local pin, no lockfile, no
install log. The only version statement anywhere in the repository is `OASDIFF_VERSION: 1.26.1` in
`.github/workflows/ci.yml:39`, and nothing local reads it.

## 3. Why there are two, and why that will keep happening

`scripts/bootstrap_tools.sh:17`:

```bash
gh release download --repo oasdiff/oasdiff --pattern '*windows_amd64.tar.gz' --clobber
```

No tag. `gh release download` without one takes **the latest release**, so the version a checkout
ends up with is a fact about the day it was bootstrapped. v1.26.0 was published 2026-07-24 and
v1.26.1 on 2026-07-27, which is the whole of the mechanism: checkouts bootstrapped between those
dates hold 1.26.0, and later ones hold 1.26.1.

Lines 12–15 are the second half of it:

```bash
if [ -x "./oasdiff.exe" ] || [ -x "./oasdiff" ]; then
  echo "oasdiff already present"
  exit 0
fi
```

A checkout that already has a binary is never upgraded, and a binary copied from a sibling worktree
is never checked at all. So the spread does not converge over time — it widens. **Seven of the
eleven checkouts here hold a binary that was never downloaded into them**: their exe carries a
sub-second mtime, which a tarball's whole-second timestamps cannot produce. Only four carry an
unmodified archive timestamp. Two of those seven copies were made on 2026-07-28 and 2026-07-29,
days after v1.26.1 was published — running the bootstrap would have fetched 1.26.1, and copying a
sibling gave them 1.26.0 instead.

This is not a bug in the script so much as a missing decision: CI pins a version and local pins
nothing, and the two were never reconciled. §7 says what to do about it.

## 4. Which binary produced the committed reports

The reports are not ambiguous about this once the git reflogs are read. Each worktree keeps its own
`HEAD` reflog under `.git/worktrees/<name>/logs/HEAD`, and a `commit:` entry there names the
checkout the commit was authored in:

| report | commit | authored in | that checkout holds today |
|---|---|---|---|
| `2026-07-29-oasdiff-determinism.md` | `6eee5db`, rebased to `3307ad2` | `m2-parsing` | **1.26.0** (`1e78ddce…`) |
| `2026-07-29-oasdiff-convergence.md` | `7a98945` | `m2-parsing` | **1.26.0** (`1e78ddce…`) |
| `2026-07-29-generated-vendor-noise.md` | `f466b98` | `m2-symbols` | **1.26.0** (`1e78ddce…`) |

`sync-m0-vendor-change` also carries `3307ad2` and `7a98945` in its reflog, but only as
`rebase (start): checkout origin/main` and `rebase (pick)` of unrelated commits — it replayed onto
them rather than producing them.

So of the two explanations the brief put forward:

- **"The binary was 1.26.0 then and has since been replaced"** — half right and half wrong. The
  reports were true when written. But nothing was replaced: the binaries that produced all three
  reports are still sitting in the checkouts that produced them, unchanged, and still report 1.26.0.
- **"The binary was already 1.26.1 and the version was recorded wrong"** — refuted. Both authoring
  checkouts hold `1e78ddce…`, which is 1.26.0 by its own `--version` and by its byte count, and
  which a third checkout holds under an unmodified archive timestamp 16 seconds before v1.26.0 was
  published. The two authoring copies carry sub-second mtimes of their own, so that last piece of
  evidence attaches to the bytes rather than to those two files.

The third explanation, which is the one the evidence supports, is that the question presupposes a
single binary and there has never been one.

**What this does not settle:** it does not prove the binary present in `m2-parsing` on the day the
determinism report ran is byte-identical to the one there now — `tools/` is outside git and has no
history, so no evidence on this machine can establish that. What it does establish is that the
simplest account consistent with every artifact (two files, two releases, an unpinned bootstrap, and
authoring checkouts that still hold 1.26.0) requires nothing to have changed, and the competing
account requires a replacement that left no trace and coincidentally restored the older version.

## 5. The numbers reproduce on 1.26.1

`2026-07-29-generated-vendor-noise.md` §2 closed on the caveat that *"72 runs on 1.26.1 is a
measurement nobody has taken"*. It has now been taken: 12 runs per pair over the same six pairs,
the same sha256-pinned inputs, against `629d435b…`.

**Every number in that report's §2, §3 and §4 reproduces exactly.**

| pair | records/run | operations/run | new kinds after run 1 | new op keys after run 1 | ops lost to the candidate |
|---|---:|---:|---:|---:|---:|
| anthropic 06-30 → 07-28 | 42 (12/12) | 18 | 0 | 0 | 2 |
| anthropic 07-23 → 07-24 | 22 (12/12) | 10 | 0 | 0 | 0 |
| openai 06-17 → 07-28 | 295 (12/12) | 31 | 0 | 0 | 28 |
| openai 07-23 → 07-28 | 8 (12/12) | 3 | 0 | 0 | 3 |
| vercel 06-18 → 07-28 | 424 (12/12) | 51 | 0 | 0 | 11 |
| vercel 07-27 → 07-28 | 40 (12/12) | 7 | 0 | 0 | 1 |

Identical on every axis the report published: record counts constant across all 12 runs of all six
pairs, the full per-rule-id distribution of §3 matching count for count, every `level` matching, the
operations-lost figures of §4 matching, nesting true on every run, and `cloudflare` still
`is_fetchable=False` at 2521 endpoints. The four pairs are bit-for-bit reproducible on 1.26.1 exactly
as they were on 1.26.0.

The same 72 runs were repeated on 1.26.0 as a control, and the result is sharper than "they agree".
**The two recorded artifacts are identical apart from the instrument record and the per-run
wall-clock seconds** — every record count, every rule-id total, every `level`, every
operations-lost figure, every curve entry, and the `cloudflare` check, the same on both, compared
field by field rather than eyeballed. For these four vendors the differ's version is not a variable.

**How the 1.26.1 runs were taken, since this checkout holds 1.26.0.** Nothing was downloaded. The
binary already present in the main checkout was copied into a gitignored scratch directory under
`.cache/`, the measurement was run with that directory as its working directory, and the scratch was
deleted afterwards. No checkout's `tools/` was written to, and both binaries were re-hashed after the
work: `1e78ddce…` here and `629d435b…` in the main checkout, unchanged. The next person to run a
measurement in either inherits exactly what was there before.

**This is the load-bearing result.** The generated-vendor report attributed Stripe's instability to
its deep recursive walk rather than to the differ's version, and hedged that attribution with the
version caveat. The caveat is now closed in the direction that strengthens the attribution: the
version was never the variable.

## 6. Stripe, and what was not re-run

The expensive measurement was not repeated in full. `2026-07-29-oasdiff-determinism.md` §8 puts one
run at 10–45 seconds and its own six-run measurement at roughly two minutes of differ time, and notes
that a single disagreeing pair reproduces the finding while an agreeing pair refutes nothing.

**Two runs were taken, on 1.26.1 (`629d435b…`), against the same pinned pair** — `v2320.json` blob
`c5d6078dd0b1392623a0d0c7a579f828ccb3a1f3` and `v2330.json` blob
`634a4b329a8e6f0d1dd13373d9f92458d0e6ee6d`, both verified against
`scripts/fetch_measurement_inputs.py` before the first run. **They disagree, so the finding
reproduces.**

| | run 1 | run 2 |
|---|---:|---:|
| records = rows | 51,982 | 374,858 |
| operation-level rows | 1,174 | 1,174 |
| seconds | 210.9 | 566.8 |

A 7.2× swing over identical bytes in one session. On the natural key the two runs share **13,108
rows of a 413,732 union** — 38,874 only in the first, 361,750 only in the second — which is the
same non-convergence the determinism report measured, on the version CI actually pins. Operation
level held at 1,174 on both runs and nesting held, consistent with §3 of that report.

**Two numbers here disagree with the report that prescribed this check, and the measurement wins.**

- §8 puts one run at **10–45 seconds**. These took **211 and 567 seconds**, on an unloaded machine,
  five to thirteen times the stated range. The 24-run convergence measurement is costed at 1,949
  seconds on that basis; at these rates it would be well over two hours. Anyone budgeting from §8
  should not.
- Run 2's **374,858 records exceed every value in the determinism report's table**, whose largest
  was 215,126. The instability's upper end is higher than six runs found.

Neither changes a conclusion — both make the instability worse than recorded, and the exemption
rests on instability. But §8's timing estimate should not be relied on, and that is a fact about the
report rather than about the differ.

**What this leaves uncovered.** Two runs over one specification pair on one machine. It does not
re-measure the **467 varying operation-level rows** of §3 — both runs here reached the full 1,174,
so this pair says nothing about the lost-operations failure mode, which is the one the determinism
report calls the real exposure. It does not re-take the rule-id distribution of §4 beyond
confirming that only the same two ids appear. It does not establish the nesting property in the
strong sense, because two identical operation sets are nested trivially. And it does not touch the
convergence curve: the convergence report's §7 gap, *"24 runs on 1.26.1 is another 32 minutes
nobody has spent"*, is still open, was deliberately not closed here, and on the timings above would
cost considerably more than 32 minutes.

## 7. Making the instrument auditable

The reason this took a day's work to settle is that the instrument version was stated in prose and
nowhere a later reader could check it. Three reports named a version; none named a file.

Two things changed, both small:

`scripts/measure_generated_vendor_noise.py` now records an **`Instrument`** — the version string and
the **sha256 of the binary that ran** — into its `--out` JSON, and refuses rather than recording a
blank. The hash is the part that earns its place: as §1 shows, the version string does not identify
the binary, because two files on this machine both call themselves oasdiff and a reader holding one
cannot tell from the name whether it is the one that ran.

The refusal is not hypothetical either. Before this change, `--version` was read without checking
the return code, so a binary that existed but could not run would have written `""` into the
artifact — a measurement that looks recorded and identifies nothing.
`tests/test_measurement_instrument.py` covers both properties, including two stub binaries that
report the same version and differ in bytes.

And the measurements themselves are now committed, beside the report they belong to, under
`docs/superpowers/reports/recorded/`:

| artifact | instrument |
|---|---|
| `2026-07-29-generated-vendor-noise-oasdiff-1.26.1.json` | `oasdiff version 1.26.1`, sha256 `629d435b…` |
| `2026-07-29-generated-vendor-noise-oasdiff-1.26.0.json` | `oasdiff version 1.26.0`, sha256 `1e78ddce…` |

Both are committed because §5 makes a claim about both, and an artifact supporting half a claim is
the problem this task exists to fix. That is the whole of the mechanism — two files, written by the
`--out` flag the script already had. No framework, no schema, no runner.

**One incident worth recording, because it is the argument for the hash in miniature.** During this
task the mutation-testing harness rewrote the script on disk while a background measurement was
starting, and the measurement imported a mutated module whose version string was the hardcoded
constant `"oasdiff version 1.26.1"`. The artifact it produced claimed 1.26.1 and carried sha256
`1e78ddce…`, which is 1.26.0. The hash caught a version string that was lying, in the first hour the
hash existed. That measurement was discarded and both runs were repeated cleanly against the
committed script.

## 8. What this does not settle, and the next task

**CI and local are pinned by two mechanisms and one of them is not a pin.** `.github/workflows/ci.yml`
names `OASDIFF_VERSION: 1.26.1` with a comment explaining exactly why it must not float — *"oasdiff's
rule identifiers are Sync's `VendorChange.kind` domain, so a floating version would silently change
the set of kinds the pipeline can see"* — and `scripts/bootstrap_tools.sh` then floats it locally.
The argument in that comment applies to local development at least as strongly, since that is where
the rule-id domain gets characterised in the first place.

`.github/workflows/ci.yml` and the rest of `scripts/` were out of scope for this task, so **this is
the next task and it is not a drive-by edit**: have `bootstrap_tools.sh` read the version from one
place that CI also reads, upgrade a checkout whose binary is the wrong version rather than
short-circuiting on presence, and decide what a developer holding the other version should see. The
measurements in §5 say the change is safe to make on the numbers — the generated-vendor corpus is
identical across the two versions — so the cost is the mechanism, not a re-measurement.

**Done.** `docs/superpowers/reports/2026-07-29-one-oasdiff-pin.md` carries it. `.oasdiff-version` is
the single pin, both installers read it, and a checkout holding another build is refused rather than
upgraded — the third question above, answered against replacement, because an upgrade in place would
overwrite the bytes §4 of this report is built out of.

**One instance of the same claim is left uncorrected.**
`docs/superpowers/reports/2026-07-29-depth-measurement.md:32` says *"`oasdiff version 1.26.0`, the
binary in `tools/`"* — the same sentence shape, carrying the same unstated assumption that `tools/`
holds one thing. That report was outside this task's ownership and was deliberately not edited. It
needs the note in §1 applied to it, and that is a one-line change for whoever owns it next.

**The idempotence exemption is unaffected and stands.** `CLAUDE.md` grants oasdiff-derived
`vendor_change` rows their exemption on the grounds that `oasdiff breaking` *"returns a different
answer every run over identical bytes on both pinned versions"*. That wording is confirmed rather
than disturbed: §6 reproduces the instability on 1.26.1, and the determinism report's own §1 table
had already measured both. Nothing here retires it, and
`docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md` still carries what would.

## 9. Commands, so a reader can re-run this

```bash
# what is installed, everywhere
for d in <each checkout>; do "$d/tools/oasdiff.exe" --version; sha256sum "$d/tools/oasdiff.exe"; done

# what the releases are, and when they were published
gh release list --repo oasdiff/oasdiff --limit 12

# which checkout authored a report
grep "commit: docs: oasdiff's nondeterminism" .git/worktrees/*/logs/HEAD

# the 72 runs, recorded
uv run python scripts/measure_generated_vendor_noise.py --runs 12 \
  --out docs/superpowers/reports/recorded/2026-07-29-generated-vendor-noise-oasdiff-1.26.1.json

# the Stripe spot check, per 2026-07-29-oasdiff-determinism.md section 8
tools/oasdiff.exe breaking .cache/specs/v2320.json .cache/specs/v2330.json --format json > run1.json
tools/oasdiff.exe breaking .cache/specs/v2320.json .cache/specs/v2330.json --format json > run2.json

uv run pytest tests/test_measurement_instrument.py -q -n0
```

Running the measurement in a checkout holding the other binary is the point, not a mistake: the
artifact records which one answered, so two readers who disagree can find out why.
