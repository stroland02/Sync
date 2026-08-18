# Static description moves to Settings; working screens carry working data

**Owner ruling, 2026-08-18:** *"in a lot of pages we have a lot of [static] cards that are just kind of
like information that's just there instead of the actual dynamic workflow or information or data … so
let's make sure any of that static, just descriptive information about the platform is actually within
settings, and settings has all that information."*

## The rule

**A screen's job is to show what is true about this codebase right now.** Anything that would read the
same on an empty database, on a fresh install, and a year from now is not that — it is documentation,
and it belongs in Settings.

**The test, applied per card:** *would this text change if the data changed?* If no, it is static and
it moves.

## The distinction that has to be drawn carefully, because getting it wrong deletes something protected

`CLAUDE.md` protects twenty-four sentences on screen and forbids deleting, shortening, collapsing or
tooltipping any of them. **They are not what this ruling is about, and here is the difference:**

| | Moves to Settings | Stays on the screen |
|---|---|---|
| **What it is** | Description of the platform | A qualifier on a number that is on screen |
| **Does it change with the data?** | No | **Yes** — it appears because of what the data does or does not contain |
| **Example** | A card explaining what the provenance rung is | *"Never measured"* beside a repository with no telemetry |
| **Authority** | This ruling | `CLAUDE.md`, and `tests/test_console_honesty_sentences.py` is the arbiter |

**The short form: an explanation of the product moves. A statement about this row stays.** A sentence
that says *we could not check* is not decoration — it is the measurement, and it is the whole reason
this console exists.

**When in doubt, keep it and ask.** Deleting a protected sentence costs a rule violation and a
correction round; leaving one static card in place for an hour costs nothing.

## What Settings becomes as a result

Settings is now two things rather than one: **the place where things are configured, and the place
where the platform explains itself.** That pairs with `M0-W317`, which already established it must
contain real settings rather than list information — **the answer is not "less information in
Settings", it is "the information belongs there and the controls belong there too."**

Groups, extending the set in `M0-W317`:

| Group | Contents |
|---|---|
| Codebases | select, add, remove — where the scope switcher lives in long form |
| Pull requests | merge policy, merge method, base branch; `immediately` refused, with the reason stated |
| Adapters | per-vendor configuration |
| Connection | the authenticated `gh` account, repositories Sync may act on, a live token check |
| **About / How this works** | **the static explanation moved off the working screens** — what a rung is, what a tier is, what the abandon reasons mean, what the gates measure |

## Per-lane

Every lane, on its own screens: **find the cards that would read identically on an empty database and
move them.** Lane G receives them into Settings. Nothing is deleted in transit — a card that moves
keeps its text, and if it turns out to be one of the twenty-four it comes straight back.
