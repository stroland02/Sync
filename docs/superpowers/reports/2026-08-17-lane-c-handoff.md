# Lane C handoff — pipeline health, the gate, and CI

**2026-08-17.** Written for a successor who cannot read the transcript. Every finished thing is
named by its commit rather than its intention, because "gate work done" is not resumable and
`CI-W308 landed at 49292ac` is.

## Where to start

1. Run `uv run python scripts/beta_gates.py`. It answers all four gates in seconds and says
   `CANNOT TELL` where it cannot answer.
2. Run `uv run python scripts/dev_up.py --check`. It answers whether the console can come up.
3. Read `docs/superpowers/BACKLOG.md`'s status section, then this lane's open entries below.

## Landed, by commit

| Unit | Commit | What it did |
|---|---|---|
| `CI-W280` | `f0aebb4` | numbering: took Lane C's own block back from the coordinator's |
| `CI-W281` | `42785ee` | filed `B151` — `main` 60 red, not environmental |
| `CI-W282` | `5b36bf5` | `gate_verdict.py`: a crashed worker stops reading as failing tests |
| `CI-W283` | `87a82cb` | the crashed-worker check reaches CI; guard for a literal `\n` in a step |
| `CI-W284` | `06cc61e` | the nightly gate was escapable three ways; mutants as negative controls |
| `CI-W285` | `c02630b` | the verdict check stops failing jobs that never ran a suite |
| `CI-W286` | `41e73a4` | filed `B153` — a 429 on an action download reads as a failed build |
| `CI-W287` | `b531f47` | gate wall-clock measured: 1215/1741/3270s → **233s** |
| `CI-W288` | `8ecc0e3` | threat model reconciled; `B97` re-scoped rather than closed |
| `CI-W289` | `69bc669` | `scripts/beta_gates.py` — the gates measure themselves |
| `CI-W290` | `9c3ac08` | beta readiness measured on every push; cannot fail a build |
| `CI-W291` | `8d45ecd` | Gate 4 reads `needs.serial.result` instead of re-running the suite |
| `CI-W292` | `141d2d8` | the staleness meter stops ignoring a re-sign |
| `CI-W293` | `5fd86d2` | threat model against the tree; filed `B165`–`B168` |
| `CI-W294` | `39736d5` | the gate job proves its own publication |
| `CI-W295` | `36c4fa1` | **the trustworthiness check was calling every CI run untrustworthy** |
| `CI-W296` | `0f209e8` | Lane C stock-take; filed `B169`–`B171` |
| `CI-W297` | `739f5d0` | the setup instructions become true, and a test executes them |
| `CI-W298` | `ae76688` | `B170` measured, `B171` closed and smaller than filed |
| `CI-W299` | `c9fe7cb` | Gate 3 watches the claim surface rather than three directory names |
| `CI-W300` | `c1317bc` | what the visual eval needs from CI; filed `B172` |
| `CI-W301` | `03974ed` | `scripts/dev_up.py` — one command brings the console up |
| `CI-W302` | `33b0c8d` | the dev loop comes up; running it found what checking could not |
| `CI-W303` | `d6304a9` | the console no longer starts against an API that did not come up |
| `CI-W304` | `222d2c4` | four subsuming clauses accounted for, one judgement each |
| `CI-W305` | `6268218` | filed `B174` — the `extract_credential` narrowing, for Lane E |
| `CI-W306` | `ac6b01a` | Gate 4 answers whether `main` is green, and says when it looked |
| `CI-W307` | `cd5cdbe` | corrected a test `CI-W306` made false, and the default that hid it |
| `CI-W308` | `49292ac` | four axes wait on `B7` and one does not |

## Open, and what each needs

**`B183` — the B97 positive controls fail under `-n auto`, pass 8 of 8 alone.** Filed today with
what is known and what is not. A leaked `sync-patch-sandbox` container had been up nine hours; the
attacker listener binds `0.0.0.0:0`, so a fixed host port is already eliminated as the cause. **Do
not assume contention** — `CI-W280` closed a near-identical symptom whose real cause was
`host.docker.internal` not resolving on Linux. This is the next thing this lane would do.

**`B172` — wire the visual eval into CI.** Parked on Lane B settling the extraction mechanism, which
is the whole of the wiring. Requirements are already written in
`reports/2026-08-17-visual-eval-what-ci-needs.md`; the load-bearing one is that token-derived
properties may gate and content counts may not.

**`B174` — `extract_credential` narrowing.** Lane E's. If it lands, `SUBSUMING` in
`tests/test_decode_handlers.py` must lose its key in the same commit or `main` reddens.

**`B165`–`B168`** from the threat-model pass, owned by Lanes A, D and E. `B165` is the one that
matters: a customer's `.sync/context.md` reaches the patch prompt unfenced while the preamble tells
the agent that unfenced lines are its instructions.

## What this lane owns

`.github/`, `scripts/` except `scripts/orchestration/`, `pyproject.toml`, `docker-compose.yml`,
`docker/`, `tests/conftest.py`, `tests/test_lint_*`, `tests/test_ci_*`, `tests/test_gate_*`,
`tests/test_leaked_database_sweep.py`, `tests/test_patch_sandbox.py`, `tests/test_sandbox.py`.

Backlog numbers: **`B183`–`B192`** (`B183` used). Work items: `CI-W280+`; `CI-W309` is the last used.

## Things a successor will otherwise rediscover

- **Run the suite with `-n auto`.** Measured 125s here and 185s on a runner, both trustworthy. The
  charter's old `-n 4` advice was a workaround for npx-lock starvation that Lane D fixed in
  `2cf2e62`, and it costs 108s a run for nothing.
- **A fresh worktree fails ~50 tests** for gitignored `tools/oasdiff.exe` and `.cache/corpus/`.
  `bash scripts/bootstrap_tools.sh` and `uv run python scripts/fetch_corpus_repositories.py`, both
  once per checkout — now in `README.md` and `CONTRIBUTING.md` as of `739f5d0`.
- **Vite binds IPv6-only here.** `127.0.0.1:5173` refuses; `localhost:5173` serves. That reads as a
  broken dev server and is not one.
- **Never chain `git push` behind the gates in one command.** `CI-W306` was pushed with a failing
  test because the push ran after the gate output nobody read. Read the gate, then push.
- **Use the file tools for multi-line content.** Shell heredocs mangled string literals twice today
  and cost a repair pass each time.
- **`git checkout <file>` on unstaged work reverts the whole file.** It cost this lane the `ci.yml`
  wiring once.

## The pattern worth carrying

Every defect this lane found in **its own** work came from executing the thing rather than asserting
about it: the bare `npm` name, the unbounded connect timeout, the readiness check satisfied by a
stale server on the same port, `--run-suite` crashing as a script, and the verdict parser calling
every CI run untrustworthy. The check-only path was tested each time, and passed each time.
