# Two sets of psycopg's exception classes, and the coverage flag that makes them

**Date:** 2026-07-30
**Scope:** M3-W102 — correct M3-W99's account of why `except psycopg.Error` fails under
`pytest-cov`, then find the real cause.
**Outcome:** the mechanism is real, it is not what either W99 or the retraction said, and it is
now reproduced in 3.27 seconds with neither coverage nor pytest involved. One clause changed in
`tests/conftest.py`. `pytest_configure`'s own control flow is untouched.

## The short version

W99 was closer than its retraction. Two sets of psycopg's exception classes really do coexist, and
`except psycopg.Error` really does fail to catch — but only under a **dotted** `--cov=<module>`
whose import reaches psycopg, and the duplication is not created by the C extension. It is created
by `coverage` deleting psycopg from `sys.modules` and importing it again.

Both earlier measurements were correct. They were taken under different `--cov` forms, and the form
is the variable nobody had isolated.

## What `psycopg_binary._psycopg` actually holds

Checkable without running a test, which is why it went first.

    exception-ish names in _psycopg: []
    BaseException subclasses exported by _psycopg: []

The extension exports **no exception classes at all**, so "`psycopg_binary._psycopg` holds one set
and `sys.modules['psycopg.errors']` exposes another" is wrong as written. What the extension holds
are internal references captured when it was initialised. In a plain interpreter there is one set
of classes and every identity check passes:

    psycopg.Error is psycopg.errors.Error = True
    psycopg.Error in ConnectionTimeout.__mro__ = True

So the static check that both the coordinator and I ran is right, and it does not settle the
question — because the duplication only exists after something has evicted the modules.

## Whether `--cov` changes the answer: yes, and only in one form

Same probe, same machine, same interpreter. `connect_timeout=2` against a closed port, so each row
costs a few seconds.

| invocation | `errors.py` executions | raised class is the current one | `isinstance(exc, psycopg.Error)` | the sweep's handler |
|---|---:|---|---|---|
| `python probe.py` | 1 | True | True | catches |
| `pytest` — no `--cov` | 1 | True | True | catches |
| `pytest --cov=sync` — **what CI runs** | 1 | True | True | catches |
| `pytest --cov=src` | 1 | True | True | catches |
| `pytest --cov=src/sync/benchmark` | 1 | True | True | catches |
| `pytest --cov=sync.benchmark.mutate` — **W99's command** | **3** | **False** | **False** | **raises** |

The bottom row reproduced on both attempts, at 2.77 s and 3.07 s. Execution counts are from
`python -X importtime -m pytest …`, counting lines for `psycopg.errors`.

**The trigger is precise: a dotted `--cov=<module>` whose import pulls `psycopg` into
`sys.modules`.** `--cov=sync` is safe because `sync/__init__.py` does not import psycopg;
`--cov=sync.benchmark` and anything below it is not, because that package does. Path-form arguments
are safe because they never name a package to import. **CI is in the safe set** —
`.github/workflows/ci.yml` runs `--cov=sync`.

## The mechanism

`coverage/inorout.py:313` resolves each `source_pkg` by importing it, inside a context manager
whose job is to undo the imports:

```python
with sys_modules_saved():
    for pkg in self.source_pkgs:
        modfile, path = file_and_path_for_module(pkg)
```

`coverage/misc.py`'s `SysModuleSaver.restore()` is the other half:

```python
new_modules = set(sys.modules) - self.old_modules
for m in new_modules:
    del sys.modules[m]
```

Importing `sync.benchmark.mutate` pulls in 77 psycopg modules, and all 77 are then deleted. What
happens on the next import is asymmetric, and the asymmetry is the whole defect:

- `psycopg/errors.py` is **pure Python**. It re-executes and builds a second set of every exception
  class. `psycopg/__init__.py` re-executes too, so `psycopg.Error` is a class from the second set.
- `psycopg_binary._psycopg` is an **extension module**. The interpreter caches it below
  `sys.modules`, so deleting the entry does not unload it and re-importing does not re-execute it.
  It keeps the references it captured the first time.

The connect generator lives in that extension. `generators.pyx:67` raises a `ConnectionTimeout`
from the **first** set; `except psycopg.Error` names the **second**. The class is absent from the
MRO, `isinstance` is False, and the handler does not catch.

**Fifteen lines, no coverage, no pytest, 3.27 s:**

    evicted 77 modules from sys.modules
    psycopg.errors re-executed           = True
    psycopg.Error is a new class         = True
    C extension module object reused     = True
    sys.modules holds one psycopg.errors = True
    raised psycopg.errors.ConnectionTimeout
    raised is the FIRST  set's class = True
    raised is the SECOND set's class = False
    isinstance(exc, psycopg.Error)   = False
    isinstance(exc, first_error)     = True

### Two corroborations that cost nothing to check

**psycopg's own handler fails too.** `Connection.connect` catches `e.Error` per address to try the
next one, and re-raises at the end through `with_traceback(None)`. Under the split that handler is
defeated by the same mechanism, which shows up twice: the traceback arrives **intact** through
`generators.pyx:67` instead of stripped at `connection.py:130`, and the wall clock **halves**,
because the exception escapes on the first address instead of both being attempted. Measured: 20 s
caught versus 10 s escaping, against `localhost`.

**Only what the extension raises is split.** A server-side error is built from its SQLSTATE by the
re-executed `errors.py`, so it belongs to the set the handler names. Measured under a deliberate
split:

    server-side SyntaxError  isinstance(exc, psycopg.Error) = True
    DROP-refusal ObjectInUse isinstance(exc, psycopg.Error) = True

This is what decided the scope of the fix below.

## What made W99 land on the wrong mechanism

Its `sys.modules` check. Having seen two class objects, it asked whether `sys.modules` held two
`psycopg.errors` entries, found one, and concluded the second set must therefore live in the C
extension. But a re-execution **replaces** the entry rather than adding one, so a count of one is
exactly what the true mechanism predicts. The check could not distinguish the two hypotheses and
was read as though it could.

That is the transferable lesson, and it is not "W99 was careless". Every number it printed was
real. What failed was a check that looked discriminating and was not — the same family as the
`st_mtime_ns` rule in `CLAUDE.md`.

## Where this leaves the retraction

`b020fb5` retracted the mechanism on the strength of a probe returning `same_class = True`. That
measurement is correct and reproducible. So is mine returning `False`. The difference is the
`--cov` form, and the retraction's conclusion — "the class-identity mechanism does not exist" — is
the one claim in it that does not survive.

Specifically:

- **Stands:** the coordinator's probe run, the 741 s full `-n0 --cov` run at 2441 passed, the MRO
  check. All three were taken in the safe configuration, where identity genuinely holds.
- **Does not stand:** that the mechanism does not exist, and that the unguarded create block is
  what W99 observed.

W99's red test was `test_a_server_that_cannot_be_reached_is_not_an_error` — one test failing inside
a running suite, not a session dying before collection. That test is reproduced here, under W99's
own command, for W99's stated reason:

    ### W99's red test, --cov=sync.benchmark.mutate, WITH the fix
    1 passed in 10.42s
    ### the same test, the same flag, WITHOUT the fix
    psycopg_binary/_psycopg/generators.pyx:67: ConnectionTimeout
    1 failed in 10.53s

**10.42 s and 10.53 s against W99's reported 10.21 s.** Its timing was accurate too. Everything it
measured was real; only the account of where the second class set came from was wrong.

## The unguarded block, confirmed independently

Read in the tree rather than taken from either party. Between the guarded connect and the guarded
sweep sits:

```python
with conn:
    conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(...))
    conn.execute(sql.SQL("CREATE DATABASE {}").format(...))
```

No `try`, no `except`. Confirmed.

**A `ConnectionTimeout` is not the likely way in.** The connect on the line above has already
succeeded, and it is issued with **no `connect_timeout` at all**, so it blocks rather than timing
out; a connect timeout cannot arrive here. The likelier way in is the one the parallel coordinator
guessed: a `DROP … WITH (FORCE)` that cannot get the lock, raising `psycopg.errors.ObjectInUse` —
measured above as a real class from a refused DROP. `FORCE` terminates the backends it can see; it
does not stop one connecting in the window, and it will not drop a template or a database the role
does not own. `DuplicateDatabase` on the `CREATE` is a second, narrower way in.

**One correction to the framing.** Because the block is unguarded it *already* fails loudly: the
exception escapes `pytest_configure` and the session dies before collection. The choice is not
between failing loudly and continuing unisolated — continuing unisolated is not what happens
today. It is between an unexplained psycopg traceback from inside a hook and a message that names
the database and says why the run cannot proceed. I agree with the parallel coordinator's
conclusion on those narrower grounds, and it is a smaller change than the argument for it implies.

**Not done here.** No reproduction, and it would alter `pytest_configure`, which every suite run on
this machine loads. Proposed, not edited.

## What changed

One clause, in `sweep_leaked_databases`:

```python
    except Exception:          # was: except psycopg.Error
        return []
```

That is the outer handler, the one wrapping `psycopg.connect`. Justified by its own stated
invariant — *"Nothing here may fail the run"* — plus a demonstrated failure. An invariant a
coverage flag can void is not an invariant.

**The inner handler was left as `psycopg.Error`, deliberately.** It exists to skip a refused DROP,
and the measurement above shows a refusal is built by the re-executed `errors.py` and is caught
either way. Widening it would be error handling for a condition that cannot occur.

**This does not change `pytest_configure`.** No statement in that hook was touched. `pytest_configure`
calls `sweep_leaked_databases`, and the change makes that call strictly less likely to raise, never
more — the only reachable difference is that a session which would have died now proceeds.

The two `test_zz_scratch_*` probes are removed. They asserted nothing, cost 20 s and 40 s, and one
of them re-raised by design, which would have turned any dotted coverage run red on purpose. What
they established is in this report and pinned by the test below.

## Mutations

Baseline `1 passed in 11.06s`; restored baseline `1 passed in 11.31s`, same count, so nothing
drifted. Harness compiles each mutant before writing it, passes `--color=no` and
`PYTHONIOENCODING=utf-8`, and reads children with `errors="replace"`.

| mutation | verdict | note |
|---|---|---|
| `M-outer` — the outer clause back to `psycopg.Error` | **KILLED**, `1 failed in 16.80s` | the change under test |
| `M-split-guard` — the child stops constructing the split | **KILLED**, `1 failed in 11.24s` | the test refuses to pass without reproducing what it claims to test |
| `M-returncode` — the exit-code assertion relaxed to `in (0, 1)` | **SURVIVED**, `1 passed` | redundant, not untested — see below |
| `M-outer+rc` — outer reverted *and* exit code relaxed | **KILLED**, `1 failed in 10.99s` | `assert "RETURNED []" in stdout` subsumes the exit-code assertion |

`M-returncode` survives because the exit-code assertion is subsumed: a sweep that raises prints no
`RETURNED` line, so the later assertion catches it anyway. The redundancy is kept because it
produces a failure message carrying the child's `stderr`, which is the traceback a reader needs.
`M-outer+rc` is what establishes this rather than assertion.

`M-split-guard` is the one that matters for honesty. A test that asserts on class identity passes
today whatever the code does, so this test asserts on the object the handler actually receives from
a real `psycopg.connect`, in a child that first proves the split occurred and fails loudly if it
did not.

## Timings, unrounded

| what | cost |
|---|---|
| minimal reproduction, no coverage, no pytest | **3.27 s** |
| probe under `--cov=sync.benchmark.mutate` | **2.77 s**, **3.07 s** |
| `test_psycopg_error_identity.py` alone | **10.80–11.29 s** |
| the pre-existing unreachable-server test alone | **20.26 s** (two address attempts) |
| W99's claim of 10.21 s on one test | consistent with a single 10 s connect timeout |
| the coordinator's full `-n0 --cov` run | 741 s, and could not reproduce — no source package to import |

Every closed port on this machine times out rather than refusing, so a connect failure costs the
full `connect_timeout` per address. The new test uses a bare `127.0.0.1` rather than `localhost` so
libpq makes one attempt instead of two, which is what keeps it near 10 s.

## Gates

Run on the merged tree — `origin/main` moved ten commits during this task, so these are figures
from the merge and not from the branch alone.

| gate | result |
|---|---|
| `uv run pytest -q` | **2507 passed, 2 skipped, exit 0, 111.91 s** |
| `uv run python scripts/lint_encoding.py src scripts tests` | exit 0 |
| `PYTHONIOENCODING=utf-8 uv run lint-imports` | `1 kept, 0 broken`, exit 0 |
| `uv run python scripts/lint_dead_links.py src --baseline …` | exit 0 |
| `uv run pytest -q -n0 --cov=sync.benchmark.mutate --cov-report=term-missing` | **2321 passed, 2 skipped, 186 errors, exit 1, 495.08 s** — see below, not this change |

The `-n0 --cov` gate is run in the dotted form deliberately, because that is the configuration the
claim is about and the only one in which the defect is reachable. Zero occurrences of
`ConnectionTimeout` or `psycopg.Error` anywhere in its output, which is the thing this task set out
to change.

An earlier `-n0 --cov` run, at the previous merge base and with the same fix in the tree, gave
**2464 passed, 2 skipped, exit 0 in 743.18 s** — within noise of the 741 s the coordinator measured.
Serial coverage costs this suite roughly six times its parallel wall clock.

### The 186 errors are a different, pre-existing defect, and `-n0` is the axis

**Not this change, and not `--cov`.** Every error is the same one:

    FATAL:  database "sync_test_12316" does not exist

The run's own database — the one `pytest_configure` created for it — disappears partway through
`tests/test_leaked_database_sweep.py`, and every later test needing Postgres errors in setup.
Attribution was measured rather than assumed:

| control | result |
|---|---|
| `-n0`, **no** `--cov`, two files | reproduces, `32 passed, 4 errors` in 32.35 s |
| `-n0`, no `--cov`, **`origin/main`'s `conftest.py` restored verbatim** | reproduces identically, `32 passed, 4 errors` in 33.36 s |
| `-n auto` full suite, same tree | **2507 passed, exit 0** |

So it is reachable on `main` without this branch and without coverage, and the parallel scheduler
hides it. That is consistent with it going unnoticed: `addopts` pins `-n auto`, and CI's coverage
step carries `|| true`.

**Recipe, 33 s:**

    uv run pytest -q -n0 tests/test_leaked_database_sweep.py tests/test_migration_corpus.py

**What I ruled out.** `pytest_configure`'s own sweep is not it — no `swept …` line is printed in a
reproducing run. Threading `exclude=<the run's own database>` through the two
`sweep_leaked_databases(ADMIN, is_running=dead_to_the_sweep)` call sites does **not** fix it, which
is what I expected to fix it and did not.

**The obvious candidate, stated as a hypothesis and not a finding.** Those two call sites pass
`dead_to_the_sweep = lambda pid: pid != os.getpid()`. Under `-n0` the test process *is* the
controller, so the run's own `sync_test_<controller pid>` reports dead to that probe where under
`-n auto` it reports alive. That is the right shape and it does not survive the `exclude`
experiment, so something else or something additional is at work and I am not going to name a cause
I could not confirm — which is the whole subject of this report.

**What would settle it:** the same instrumentation that failed here for an unrelated reason. A
`pytest_runtest_teardown` plugin reporting whether the database still exists, run per test over
that one file, names the culprit test in one pass. My attempt hit
`[Errno 10109] getaddrinfo failed` resolving `localhost` — a Windows resolver failure under the
load of this session's own subprocess churn, not a logic fault — and I stopped rather than fight
the machine.

**Not fixed here.** It is a different defect in a file two earlier tasks already investigated, its
fix belongs in `tests/test_leaked_database_sweep.py` rather than in `conftest.py`, and it wants its
own failing test first.

**Settled by M3-W105 — `docs/superpowers/reports/2026-07-30-n0-is-broken.md`.** The hypothesis
above was right, including where the fix belongs, and `exclude` on those two call sites is what
fixes it. The missing piece was that under `-n auto` the run's own database carries a *second*
pid — the controller's — which the same probe reports alive; there is no controller pid under
`-n0` to be spared by. The `exclude` experiment that failed here was taken under the full-suite
dotted `--cov=sync.benchmark.mutate` configuration rather than under the 33 s recipe, so the two
are not compared, for the reason this report gives.

## What is still open

**The split defeats any `except psycopg.X` in a dotted coverage run, not only this file.** There
are four such handlers in the repository — three in `tests/conftest.py`, one in
`tests/test_schema_convergence.py`. Only the one with an unconditional invariant was widened. The
rest are correct Python defeated by an interpreter-level identity split, and the proportionate fix
is to prefer path-form `--cov` arguments rather than to widen handlers across the codebase.

**This is upstream behaviour, not a psycopg bug and not a coverage bug exactly.** `sys_modules_saved`
is sound for pure-Python modules and unsound for any package with a compiled half. It is worth an
upstream report; nothing here depends on one.
