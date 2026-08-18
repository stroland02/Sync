# Recording `main-is-green` against `HEAD`, at the cut, in one command

**2026-08-18, Lane C, `CI-W389`.** Gate 4's second clause is the one that can be closed on Wednesday
morning if somebody knows what to type. This is what to type, what has to be true for it to count,
and what it now refuses to do.

## The command

```bash
uv run python scripts/beta_gates.py --run-suite
```

That is the whole of it. It runs the suite, judges it with `gate_verdict` rather than an exit code,
writes `.cache/suite-verdict.json`, and every later `beta_gates.py` reads that record until the tree
moves. **Budget four to five minutes of wall clock and about ten seconds of attention.**

## What has to be true for the record to describe `HEAD`

Three things, and until `CI-W389` only the first was checked.

1. **The suite has to produce a summary line.** A run whose worker died prints `F` against tests
   that never ran, so "is `main` green" cannot be read off an exit code. `gate_verdict` answers
   this and an untrustworthy run is recorded as untrustworthy rather than as a failure.
2. **The tree must not move during the run.** `head_commit()` was read *after* the four-minute
   run, so a merge landing meanwhile produced a record naming a commit whose tree nobody measured.
   With four lanes landing hourly that is not a corner case. `HEAD` is now pinned before the run
   and compared after; if it moved, **nothing is recorded** and the message names both commits.
3. **The worktree must be clean.** A commit names a tree; an uncommitted edit means the suite
   measured something no commit holds. Recording it against `HEAD` would claim that commit is green
   when what passed was the commit plus somebody's unsaved work, and nothing later could tell them
   apart. Now refused, naming the fix.

**Neither refusal is a failing gate.** Both are `CANNOT_TELL`, which is what this script says
everywhere else when it could not look. The failure they replace was worse than a red gate: a
confident green about a tree that never existed — the same shape the Gate 3 walk caught on itself,
where a signature landed forty-one seconds after a change it had not seen.

## Running it at the cut

- **Run it in the worktree the gate will be read from.** `.cache/` is gitignored and per-worktree,
  so the record does not travel. This is the one precondition the command cannot check for you.
- **Run it when nothing is landing.** Not a rule, an arithmetic: the run takes minutes and the
  guard will refuse if a merge lands inside them. At the cut the console is frozen anyway.
- **Commit or stash first.** The dirty-tree guard will otherwise refuse, correctly.

If it refuses, the message says which of the three failed and what to do. There is no procedure to
remember beyond the one line above.

## What this does not do

It does not make Gate 4 pass. Gate 4 has two other clauses — dead links in `src/`, and the sandbox
being built but unwired (`B97`) — and `main-is-green` is only the clause that decays. This report is
about making that clause recordable in one minute rather than about the gate's verdict.
