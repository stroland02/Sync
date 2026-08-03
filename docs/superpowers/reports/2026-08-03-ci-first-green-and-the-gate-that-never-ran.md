# CI goes green for the first time, and the gate that had never run

**Date:** 2026-08-03
**Run:** `30810733369` — the first fully passing build in this project's history.
**Commits:** `4d2a4c3`, `88276fa`, `a1075c2`, all on `main`.

## What was wrong

Three defects, discovered in sequence because each one was hiding the next.

**The corpus digests were platform-dependent.** Fixed before this session's window opened
(`scripts/fetch_corpus_repositories.py` now forces `core.autocrlf=false` and `core.eol=lf` on
checkout, and both the walk and the digest order by codepoint rather than by `Path`
comparison). Confirmed here: all five trees materialise `ok` on Windows and on the Linux
runner, against the same pinned digests.

**The binding gate had never run on a runner.** `scripts/score_corpus.py` verifies a staged
symbol map before it scores anything. That map lives in gitignored `.cache/specs/`, and no step
in the workflow produced it — so every run that got as far as scoring was refused with `no
symbol map at .cache/specs/symbols.json`. The corpus fetch was failing earlier in the same job
for longer, which is the only reason nobody noticed that the one quality number this repository
gates on had never been measured in CI.

`benchmark/corpus/symbol_map.yaml` did record how to rebuild the map — in prose. Prose is not a
step a runner can execute, and that gap *is* the defect.

**A test failed on Linux and said nothing about why.**
`test_a_finding_reaches_a_verified_patch_through_the_real_graph` reported
`assert 'abandoned' == 'verified'` and nothing else. No production code had changed since the
last run whose suite was green, so the cause was environmental — but that run executes a
compiler and a package download, and the message could not tell a broken toolchain from a
broken patch.

## What was done

`scripts/stage_symbol_map.py` turns the prose into a command: build from a pinned
specification, compare against the pinned digest, and **refuse before writing** rather than
after. A refusal leaves whatever was already staged untouched, because `.cache/` is
per-worktree space several workers share and a rebuild that truncated the file on its way to
failing would break a run that was scoring correctly.

Measured across `v2200`, `v2300`, `v2330` and `v2345`: one digest, 272 symbols. The SDK
document is deliberately not read, matching how the pin was taken — both forms produce the same
digest, and passing the argument anyway would make the output depend on whether a large
optional file happened to be staged.

`tests/test_ci_stages_the_corpus_inputs.py` asserts position within the job that scores, rather
than the workflow containing the right words somewhere: a step order that looks right and
stages nothing reads as a passing job on any run where the gate is never reached. Proven able
to fail by deleting the step and watching it go red.

`_why(state)` in `tests/test_pipeline_composes.py` renders `abandon_reason`, `diagnostics`,
`verify_ok`, `prepare_ok`, `verifiable`, `verify_gap`, `static_fatal`, `fatal`, `tier`,
`routing_row`, `static_attempts`, `replay_outcome` and `replay_reason` into the assertion.
Costs nothing on a pass; turns the next failure into a diagnosis. Verified by flipping the
expected value and reading what printed.

Then one more, found only because the staging step could finally run: `fetch_measurement_inputs.py`
shells out to the `gh` CLI, which refuses to run inside Actions without `GH_TOKEN` even against
a public repository. The workflow's own token covers it, scoped to that single step.

## The numbers, on a runner

```
Fetch the frozen corpus       five trees, all ok
Stage the pinned symbol map   5f71dcd3bec1…  272 symbols
Tests                         2772 passed, 7 skipped
binding precision   1.0000    floor 1.0000   n=26
binding recall      1.0000    floor 1.0000   n=26
falsifiable negatives    7    floor 7
pairs scored            17    floor 17
Every floor cleared.
```

The same chain was run locally first and produced the same verdict, which is what answers the
question the line-ending fix left open: **the score did not move.** That had to be measured
rather than reasoned about, because `read_checkout` translates CRLF on read and the argument
that the mapping was therefore unmoved is exactly the kind of argument a gate exists to check.

## What this does not establish

The floors are directional, over a synthetic reference. `scripts/score_corpus.py` prints the
biases in full every run and they are unchanged by any of this: the break is mechanical and
local, the distribution is the generator's rather than any vendor's release history, and
precision has almost no way to fail because the generator refuses a tree where an untargeted
call site already carries the changed dependency. A binder that scores well here has been shown
to handle the mechanical case and nothing more.

What is new is only that the number is now measured somewhere other than one person's laptop.
