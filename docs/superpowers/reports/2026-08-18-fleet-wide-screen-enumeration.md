# Which screens exist only fleet-wide, and what each one costs under a workspace root

**The unit the owner asked for before item 1 is built.** `2026-08-18-owner-console-review.md` records
the instruction: a **workspace**, selected or created, connected to **one codebase**, scoping every
page, with **no show-all**. That replaces the hierarchy root, so it is a specification amendment and
not mine to absorb. What *is* mine, and what this is, is the consequence check that document asks
for: *"Deleting the fleet root may orphan screens that have no scoped equivalent, and each of those
is a decision — build the scoped version, or delete the screen. Enumerate them before building
anything."*

Every row below is checked against `src/sync/api/app.py` and `schema.sql` rather than recalled.

## The headline, because it decides how big item 1 is

**Three of the eleven console screens can be scoped today by passing a parameter that already exists.
One is blocked by a bug. Three cannot be scoped at any price, because the schema has no column to
scope them by — and those three are the decision the owner has to make.**

Nothing here is a styling question. The last group is a data-model question wearing a screen.

## Group A — already scoped. No work, no decision.

| Screen | Route | Scoped by |
|---|---|---|
| Codebase | `/repositories/:repoId` | path parameter |
| Vendors (list) | `/repositories/:repoId/vendors` | path parameter, `M14-W371` |
| Signals | `/repositories/:repoId/observed` | path parameter |

These become the workspace's own pages unchanged.

## Group B — fleet-wide today, scopable now, because the payload already takes `repo_id`

Each of these needs a console change only. No API change, no schema change.

| Screen | Route today | The payload already accepts | Evidence |
|---|---|---|---|
| Detectors | `/detectors` | `repo_id` query param | `app.py:354` — `detector_reader(repo_id=request.query_params.get("repo_id"))` |
| API service detail | `/vendors/:vendorId` | `repo_id` query param | `app.py:229`, `:245` — narrows findings *and* the severity roll-up together |
| Binding surface | `/bindings/vendors/:vendorId/operations/:operationId` | `repo_id` query param | `app.py:320` |

**Detectors is the significant one.** The screen currently says on its own face that it is a
fleet-wide aggregate and offers *"Open this screen from a repository to narrow it to that codebase"* —
so the scoped mode is already designed and already described; only the address is unscoped. Under a
workspace root it becomes `/repositories/:repoId/detectors` and that sentence gets shorter.

## Group C — blocked by a bug, not by a design question

| Screen | Route | Blocker |
|---|---|---|
| Coverage / index panels on Codebase | `/api/repositories/{repo_id}/coverage` | **B147** |

`app.py:422-423` declare `/coverage` and `/observed` with `{repo_id}`, Starlette's **default** path
converter, which cannot match a value containing `/`. `:428-429` already use `{repo_id:path}` and
carry a comment saying why. Every repository whose id is a `host/owner/name` triple 404s on exactly
those two routes. This is P0 item 1 of the ship plan and it is Lane E's one-line fix — but it is
listed here because under a workspace root **the workspace's own home page is one of the screens it
breaks**, which raises its cost.

## Group D — cannot be scoped at any price. **These are the owner's decisions.**

The schema has no column to scope these by. This is not a missing filter; it is a missing fact.

| Screen / panel | Route | Why it cannot be scoped |
|---|---|---|
| Runs | `/api/runs` | `RunRow` carries no `repo_id`. Nothing in the transport says which repository a checkpoint thread belongs to (**B149**) |
| Repair record / corpus | `/api/corpus`, `/api/corpus/health`, `/api/corpus/abandonment` | `migration_outcome` **stores no `repo_id` at all**, and `app.py:20` records that as a deliberate schema decision |
| Adapters (on Settings) | `/api/adapters` | Deliberate, and recorded at `app.py:76-78`: *"an adapter is a property of the deployment rather than of a repository"* |

**Three options for each, and they are genuinely different products:**

1. **Add the column.** `migration_outcome` gains a `repo_id`, `RunRow` gains one. This is a schema
   change plus a backfill decision for existing rows, and it is not console work. It makes the
   workspace model complete.
2. **Delete the screens.** Honest and cheap, and it loses the repair record — the thing that proves
   the loop closes, which is Gate 1's whole subject.
3. **Admit a second scope that is not the workspace.** Some facts are true of the *deployment* rather
   than of a workspace: which adapters are attached, what this deployment watches. `app.py:76-78`
   already argues this for adapters and argues it correctly. Under this option Settings survives as
   deployment-level, and Runs and the corpus either join it or take option 1.

**My reading, offered as a recommendation and not a ruling.** Option 3 for adapters, because the
argument for it is already written down and correct. Option 1 for runs and the repair record,
because a repair record that cannot say which codebase it repaired is weak evidence for the claim
the product is built on. Option 2 for nothing — every screen in this group is load-bearing for a
gate.

## Group E — the root itself, which is the amendment

| Screen | Route | What happens to it |
|---|---|---|
| Overview | `/` | This **is** the fleet root the owner is removing |

Under the instruction it stops being a cross-repository index and becomes **workspace selection and
creation**. That is a different screen with a different question, not a restyled one.

Two things on it need a destination, and neither is obvious:

- **The four fleet counts** (`FleetFacts`) read `/api/overview`, `/api/runs`, `/api/detectors` and
  `/api/corpus` fleet-wide. Two of those four are in Group D. A workspace-scoped version can carry
  two of the four counts honestly and cannot carry the other two.
- **The protected absence sentence** — *"a repository configured but never indexed has no row in the
  repository list below, and the same absence as a repository nobody ever configured"* — names *the
  repository list below*. If that list becomes a workspace picker, the sentence still has a referent.
  If it becomes something else, the sentence must move with its referent, and
  `.claude/rules/console-surface.md` forbids shortening it on the way.

## What I have NOT done, deliberately

I have not touched the hierarchy, `GRAPH_LEVELS`, the route registry's regions, or any screen's
scope. `.claude/rules/console-hierarchy.md` makes the hierarchy the specification's and records why:
three plans built a different one and a reconciliation found three of eleven routes matching, four
levels invented and two reparented. **The owner's instruction is the ruling; the specification
amendment is what makes it buildable, and that is the owner's to record.**

## What this list unblocks, in order

1. The owner rules on **Group D** — three screens, three options above.
2. The specification's `:427-445` block gains a dated amendment replacing the `Fleet` root with
   `Workspace`.
3. Group B is then three console changes and no API work.
4. **Only then** the chrome items (3–8). The owner's own sequencing note is right: compacting a
   sidebar whose contents are about to change is work done twice.
