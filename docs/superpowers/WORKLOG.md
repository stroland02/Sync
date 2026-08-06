# Work items

One line per unit of work, in the form `M<milestone>-W<n>`. The number is a single sequence across
the whole project, never restarted per milestone — `M3-W125` and `M4-W126` are consecutive — so a
number identifies a piece of work without needing its milestone to disambiguate it.

The convention is not new. Work items ran from `W67` to `W125` under M3, in commit subjects and
dispatch briefs, and the register lived in an orchestration board that is no longer readable. This
file is that register, in the tree, so the sequence survives a session ending.

**Assigning one.** Take the next number, add the row before you start, and put the identifier in the
commit subject: `feat: M4-W131 ...`. A work item is one reviewable unit — the thing a brief asks for
or a tick takes — not one commit and not one file. Several commits under one number is normal; two
numbers for one change is not.

**A row is a fact, not a plan.** `landed` means the commit is on `m4-dashboard` and gated. Anything
else says what it actually is. A row whose state stops being true is a row to correct, and correcting
it belongs to whoever notices.

M4 continues the sequence at 126. Everything before that is in `git log`.

| Item | Subject | State | Where |
|---|---|---|---|
| M4-W126 | The Pull Request level and its evidence bundle | landed | `c808854`, `d0e316f` |
| M4-W127 | The Signals level: three roles, and the fifth kind of nothing | landed | `3855fd4`, `b39dcde`, `87f0d7f`, merged `e4284ae` |
| M4-W128 | Technical debt named as the scaling constraint in `CLAUDE.md` | landed | `d21ff71` |
| M4-W129 | The npx race that reads as a bad patch, and B99 | landed | `6d1de98` |
| M4-W130 | Repository scope on every level below Codebase — B92 closed | landed | `a628e77`, merged `e79fb5b` |
| M4-W131 | The expansion slice and four cold-start briefs | landed | `7d8e798` |
| M4-W132 | M4.5 split out so M4 can close | landed | `861673b` |
| M4-W133 | The session record a worker can actually open | landed | `0c6eb94` |
| M4-W134 | Reconcile the branch with `main`, and take the by-id read | landed | `99f542b`, `3962fcc` |
| M4-W135 | Filters that compose with repository scope — B90 slice 1 | landed | `f84e334` |
| M4-W136 | The review wave: one Critical, five Important, and an error surface | in flight | `briefs/2026-08-06-m4-review-wave.md` |
| M4-W137 | The conformance measurement against the fourteen invariants | in flight | `briefs/2026-08-06-m4-conformance-measurement.md` |
| M4-W138 | The work-item register back in the tree | landed | this file |
| M4-W140 | The decode census accounts for the borrowed wrapper's teardown | landed | `tests/test_decode_handlers.py` |
| M4-W139 | The backlog stops describing a console that no longer exists | landed | five entries closed, B90 and B94 corrected, B99 collision resolved |
