# Owner console review, 2026-08-18: ten items, and one of them amends the specification

The owner ran the console at `localhost:5173` and gave ten items. Recorded verbatim in substance,
grouped by what each one costs, because they are not the same size and one of them is not a styling
change at all.

## Item 1 is a hierarchy change and it needs the owner's ruling recorded, not a plan's

**What was asked:** *"we should be selecting a workspace or creating a workspace which then connects
to a codebase which then has all the services attached to the codebase … every single component or
tab or page corresponds to a workspace/codebase, so there should not be a show-all functionality."*

**Why this cannot just be built.** `.claude/rules/console-hierarchy.md` makes the hierarchy the
*specification's*, never a plan's, and names the authoritative block —
`specs/2026-07-25-sync-self-maintaining-apis-design.md:427-445`. That block's root is **Fleet**:

> `Fleet` — every repository the index has seen … **an index into the level below, never a
> substitute for it** → `Codebase (the selected repository)` → `API Services` → …

The rule exists because three plans previously built a different hierarchy and nobody noticed until a
reconciliation found three of eleven routes matching, four levels invented and two reparented. **So
this is exactly the change that must be ruled and written into the spec rather than absorbed.**

**What the change actually is.** It replaces the root. Today's root is *Fleet*, a cross-repository
index. The owner's root is a **Workspace**, which is *selected or created*, connects to **one
codebase**, and scopes everything beneath it. Fleet's "index into the level below" role is exactly
what "show all" is, and the owner is removing it.

**The tension worth stating before it is implemented, because it may change the answer.** The
existing spec calls Fleet *never a substitute* for the codebase level — it was already trying to stop
fleet-wide views standing in for per-repository truth. **The owner's change achieves that more
strongly by deleting the level.** So this reads as the same intent taken further, not a reversal —
but the spec block still has to say so, and the owner still has to be the one who says it.

**One consequence to check rather than assume:** several screens currently exist *only* fleet-wide.
`M14-W365` already established that `/api/detectors` discards finding rows as it aggregates and that
every findings view requires a vendor. **Deleting the fleet root may orphan screens that have no
scoped equivalent**, and each of those is a decision — build the scoped version, or delete the
screen. Enumerate them before building anything.

## Item 2 is a real interaction rule and it is easy to get backwards

**What was asked:** *"do not limit buttons based off where you're currently looking."*

An action that disappears depending on the current screen teaches a user that the product is
unpredictable, and it is the same failure as an absent option reading as an oversight. **Actions stay
present and explain themselves when unavailable**, rather than vanishing. This pairs with the
`immediately` refusal already recorded: *state the refusal, do not omit the control.*

## Items 3-8: the sidebar and page chrome

| # | Item | Note |
|---|---|---|
| 3 | Remove the sidebar's scrollbar | Implies the sidebar must fit without scrolling, which is item 6's real driver |
| 4 | Move the collapse control to the top, beside the "Console" wordmark | |
| 5 | Compact the sidebar | |
| 6 | Compact the pages | |
| 7 | **Remove the page header above each page** | *"they already describe what they do."* This deletes a component the interface-originality rule lists as a convention of the form. Deleting it is allowed; it is ours to decide |
| 8 | Reference how Orca constructs its sidebar | See the boundary below |

**On item 8 and `interface-originality.md`.** That rule was amended on 2026-08-06 precisely for this:
**a persistent navigation rail and a second contextual level inside it are conventions of the form,
and learning them from anything is permitted.** What is not permitted is a component built by looking
at a screenshot, their copy, their iconography, or the specific arrangement that makes their sidebar
recognisably theirs. **Take the structure. Do not take the rendering.**

**The owner supplied a screenshot of it. Read structurally, these are the conventions worth taking:**

- **One top row carrying wordmark, overflow, panel-collapse and history controls together.** This is
  item 4 already solved — the collapse control belongs in that row, not floating in the list.
- **Flat, icon-plus-label rows with no section heading above the first group.** Tight vertical
  rhythm; small, uniform type.
- **Search as an inline field in the rail**, not a route.
- **Quiet section labels with their actions inline on the same line** (filter, add, new). Actions
  live in the section header rather than in a page toolbar — which is part of how item 7 becomes
  possible: delete the page header, and the actions have somewhere to go.
- **Nested disclosure**: group → item → children, each level indented and collapsible, with the
  child count stated on the parent row.
- **Right-aligned metadata** on child rows, so the left edge stays a clean scan column.
- **An inline dismissible notice** for transient state, rather than a modal or a banner.
- **A pinned bottom utility bar**, outside the scrolling region.

**The one element we must not take, and it is the one an agent copying this would reproduce first.**
Its child rows carry **status dots**. `CLAUDE.md` refuses those by name — no status dot, no traffic
light, no green dot, no liveness pulse — and the reason applies exactly here: nothing in our data
distinguishes a run parked on a customer's CI from one that has died. **Take the row structure and
the right-aligned metadata; render outcome as a recorded value from a closed vocabulary, legible
without its colour, which is the badge form the same rule already permits.**

## Item 9: the interface is bland, and themes are wanted eventually

**Themes are a change to a recorded ruling, so flag it rather than starting.** `DESIGN.md:79` records
*"the light theme — dark-only stands"*. A theme system reverses that. It is also **not Wednesday
work**: the audience is an investor asking whether the product is real, and a second palette answers
nothing they will ask. **Recorded as wanted, scheduled after Wednesday.**

"Bland" is actionable now and separately from themes — density, type range and composition are all
measurable and all inside the current dark-only palette.

## Priority against Wednesday

**P0, because they change structure and everything else sits on top:** items 1 and 2.
**P1, cheap and visible:** items 3, 4, 5, 6, 7, 8.
**Post-Wednesday:** item 9's theme system.

**Sequencing note.** Item 1 changes what screens exist. Items 3-8 style the shell those screens sit
in. **Do item 1's enumeration first** — which screens survive, which need a scoped version, which are
deleted — because compacting a sidebar whose contents are about to change is work done twice.
