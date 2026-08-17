# Lane C stock-take: what is trusted here without having been checked

**2026-08-17.** Asked to walk CI, the gates, the sandbox tests and the developer loop and say what a
design partner or a second engineer would hit that the scope document does not name. Ordered by what
I would refuse to ship without, not by what is imaginable. Where I say something is fine, the
evidence is quoted; an absence of complaints is not evidence.

The prompt for this pass was that I have spent the day finding things that looked green and were
not. The first thing this pass found was mine.

---

## 1. My own trustworthiness check failed `test` on every push — FIXED, `CI-W295`

Run `32047325280`, `test` job. pytest printed:

```
======= 1 failed, 3892 passed, 7 skipped, 4 warnings in 74.73s (0:01:14) =======
```

and `gate_verdict` reported `UNTRUSTWORTHY: the run printed no summary line`.

pytest prints that tally bare on a narrow terminal and wrapped in `=` on a wide one. Every fixture
in `tests/test_gate_verdict.py` was hand-written from a local run, so all of them carried the bare
form and the anchored pattern never met the form a runner produces. **The check was correct against
its own fixtures and wrong against reality**, which is precisely the shape it exists to catch.

The cost was not the wrong word. It runs as a step that may fail its job, so the eight steps after
it never ran on any push:

| Step | Conclusion |
|---|---|
| 16 Stage the pinned Stripe specifications | skipped |
| 17 Stage the pinned symbol map | skipped |
| 18 Score the frozen corpus | skipped |
| 19 **Binding floors over the frozen corpus (gated)** | skipped |
| 20 **Pipeline rehearsal smoke (gated)** | skipped |

Two of those are gates. A check written to stop a run being misread was misreading every run and
taking real coverage down with it. **A false alarm is not the harmless direction when something acts
on the alarm** — that is the general lesson and it is worth more than the regex.

Fixed and landed. The next push is the proof, and nobody should record this as closed until steps
16–20 are observed running.

## 2. Nothing exercises a cold clone — B169

`tests/test_day_one_path.py` is twelve tests and every one of them is structural: that each command
in the Quick start resolves against the real argparse surface, that the README names every
authenticated tool, that the API and CLI agree on a default DSN, that `--repo` refuses a filesystem
path. Those are worth having and they are what `B130` was for.

**None of them runs anything from an empty checkout.** The claim they support is "the documentation
describes commands that exist", not "a person who follows it gets a working install".

The gap is measured rather than theorised. From this session: a fresh `git worktree` fails about
fifty tests purely for missing gitignored `tools/oasdiff.exe` and `.cache/corpus/` — 47 ×
`FileNotFoundError: oasdiff not found` and 3 × `RuntimeError: Corpus repository 'furever' is
missing`. That reads as a broken repository to anyone who has not been told, and the person most
likely to hit it is the second engineer or the design partner, because everyone already here has a
warm checkout.

This is the one I would most refuse to ship without, now that item 1 is fixed. A self-serve beta
whose first hour is spent diagnosing gitignored artifacts does not get a second hour.

## 3. CI runs `-n auto` while every lane is told not to — B170

`pyproject.toml:99` is `addopts = "-m 'not e2e' -n auto"`, and CI's `Tests` step is a bare
`uv run pytest`, so the runner inherits `-n auto`. The charter tells every lane to use `-n 4`
because `-n auto` crashed an xdist worker outright on this host.

I am **not** claiming this is currently breaking CI, and I want to be precise about that: the cause
of the local crashes was starvation on the npx resolve lock, which Lane D fixed in `2cf2e62`, and I
have no measurement of `-n auto` on a Linux runner since. What I am claiming is that the guidance
and the configuration disagree, and that until item 1 was fixed **CI could not have told us** if a
worker had died there — the verdict check that would have said so was itself reporting nothing
useful.

Worth a measurement, not a change. See what I would argue against, below.

## 4. The container boundary does run on the runner — this one is fine, with evidence

`test_patch_sandbox.py`'s docker-marked tests skip when no daemon is reachable, and the concern
would be that they therefore never run anywhere and B97's boundary is proven only on one laptop.
They do run: the runner initialises a daemon before the suite —

```
Docker daemon API version: '1.48'
Docker client API version: '1.48'
```

— and the skip is conditioned on reachability rather than declared unconditionally. `CI-W280` also
fixed the reason both positive controls were disarmed there (`host.docker.internal` does not resolve
on plain Linux Docker Engine), so what runs on the runner now asserts something.

I checked this expecting to find a hole and did not. Stated because a report that lists only
problems cannot be told from a selective one.

## 5. The beta meter's own blind spot — B171

`beta_gates.py` reports Gates 1 and 2 as `CANNOT TELL` in CI because CI has no corpus, which is
correct and deliberate. The blind spot is that **nobody is measuring the gates anywhere that has
one.** The local run is the only measurement that can answer them and it happens when a person types
the command.

I am not proposing a database in CI — see below. I am naming that "readiness is measured" is
currently half true: two gates are measured continuously and two are measured when somebody
remembers.

---

## What I would argue against

**Do not give the `beta-gates` job a Postgres service.** It would make Gates 1 and 2 answerable in
CI, and the answer would be wrong: an empty database read as a measurement of zero is the exact
absence-versus-zero error the console refuses on every screen, committed by the repository about
itself. `CANNOT TELL` with a stated reason is the honest output and it should stay.

**Do not make the gate job fail the build.** A red build on a gate nobody promised to have met today
teaches every lane to ignore CI, and an ignored CI is worse than none. `--exit-zero` for verdicts
and a real failure for a crashed script is the distinction, and it should not be collapsed for
tidiness.

**Do not change CI to `-n 4` on the strength of item 3.** The local crash had a cause and the cause
is fixed. Changing a setting because it once correlated with a symptom is how a workaround outlives
its reason — the charter is already carrying `-n 4` for a reason that expired. Measure `-n auto` on
a runner first; if it is clean, retire the guidance instead of spreading it.

**Do not write a test that runs a full cold clone in CI.** Item 2 wants a check, not a ceremony. A
script that verifies the bootstrap contract — that `bootstrap_tools.sh` and
`fetch_corpus_repositories.py` produce exactly what the suite refuses without, and that a missing
one produces a message naming the script — buys most of it for a fraction of the wall clock. A
fifteen-minute cold-clone job gets disabled the first week it is flaky.

---

## What I could not check

- **Whether `-n auto` is safe on a Linux runner.** Needs a run to observe, and CI could not have
  reported a dead worker until an hour ago.
- **Which seven tests skip on the runner.** The suite does not run with `-rs`, so the count is
  visible and the names are not. Adding `-rs` is a one-word change to a step I own; I did not make
  it inside this pass because it belongs with the `-n auto` measurement rather than on its own.
- **Whether any deployment outside this tree sets `SYNC_API_HOST`.** This is `B166`'s severity and it
  is not knowable from here.
