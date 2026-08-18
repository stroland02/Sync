# One region, one of each page, and the word is workspace

**Owner ruling, 2026-08-18, marked mandatory:** *"The sidebar has the same pages but different as
well — there's across all repos and then within a repository, the same pages. We need to clean this up
and there should only be one of each … all these pages should be per codebase but we want to call it a
workspace, not 'within a repository' … we want to be able to create different workspaces … the entire
dataset should be based off a workspace, which will most likely be a codebase. This is mandatory."*

## The duplication is real and here it is

`web/src/lib/routes.ts` declares **two regions — `root` (5 entries) and `repository` (7)** — and they
overlap by name:

| root | repository |
|---|---|
| `/` → **Codebases** | `/repositories/:repoId` → **Codebase** |
| `/vendors/:vendorId` → **Vendor** | `/repositories/:repoId/vendors` → **Vendors** |
| `/detectors` → Detectors | `/repositories/:repoId/services` → API services |
| `/bindings/…` → Binding surface | `/repositories/:repoId/observed` → Signals |

**`Vendor` and `Vendors` are the same page twice**, once unscoped and once scoped. So are `Codebases`
and `Codebase`. That is what the owner is seeing and it is not a rendering artefact — it is in the
registry.

## The ruling

1. **One region. Every page is scoped to the selected workspace.** The `root` region is deleted, not
   relabelled. A page that cannot be scoped does not belong in the navigation.
2. **The word is `workspace`.** Not repository, not codebase, in the interface. A workspace *is*
   backed by a codebase — that stays true in the data — but the reader's word is workspace.
3. **One of each page.** `Vendors`, `Signals`, `API services`, `Binding surface`, `Detectors`,
   `Findings` — each exists once, beneath the selected workspace.
4. **Workspaces can be created**, selected and switched, and that lives in the switcher and in
   Settings — never as a listing on a working page (`M0-W315`).
5. **The entire dataset is workspace-scoped.** Every route, every query, every panel.

## What this supersedes and what it completes

It completes `M0-W315` and `M0-W316` rather than contradicting them. Those said selection is chrome
and the Overview is the codebase. **This says the same thing about *every* page**, and it supplies the
word. `M0-W327`'s dead sidebar buttons dissolve here too: nine of twelve routes needed a param and had
no source for it — with a selected workspace, they all have one.

## Reference, and what to take from it

The owner supplied the Orca sidebar earlier and now points at Supabase's per-project layout. **Both
solve the same problem the same way and it is worth stating as one pattern:** a project is chosen
once, at the top, in a switcher — and everything below it is that project's. Neither offers a
"across all projects" mirror of each page. **That absence is the design**, and it is what we are
adopting.

Take: the switcher at the top of the rail carrying the current scope and the means to change or
create one; a single flat set of destinations beneath it; grouped section labels; the pinned utility
row at the bottom. **Refused, unchanged: their status dots.**

## Ownership, because this touches a shared file

`web/src/lib/routes.ts` is the single source of truth for routing, navigation and the command palette
at once. **Lane B owns this change** — registry, `app-frame`, switcher — and every other lane adapts
its own feature to the routes that result. **No other lane edits `routes.ts`.**

## The one thing to be careful about

`routes.ts` carries `level` against `GRAPH_LEVELS`, and `.claude/rules/console-hierarchy.md` makes the
specification the authority for the ladder. **Collapsing the regions is a navigation change, not a
hierarchy change** — a level with no route still belongs in `GRAPH_LEVELS`. Do not delete levels while
deleting the region.
