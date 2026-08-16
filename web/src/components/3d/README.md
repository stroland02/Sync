# 3D graph view — declined on the merits, for now

This directory holds no components. That is a decision, not an oversight, and the two halves of
it do not cancel each other out.

## The owner wants the capability

`three`, `@react-three/fiber` and `@react-three/drei` are installed in `web/package.json` and stay
installed. The owner reversed an earlier recommendation to remove them
(`docs/superpowers/plans/2026-08-05-sync-console-design-system.md`, "The three deltas between the
specification and the tree", item 2): the project is not committing to a plain interface, and
nothing about the argument below is a case for uninstalling anything. Keeping a package for a
condition that has not yet been met is not the same as declining the capability.

## A spatial view is declined, and the reason is a correctness argument, not a taste one

The API Dependency Graph is real — call site → binding → vendor operation → vendor change — but it
is shallow (depth three, bipartite at every hop) and it has no spatial fact anywhere in it: no
depth, no elevation, no coordinate of any kind. A camera adds nothing a layered 2D diagram would
not already show.

The count that matters is the console's own claim: a view whose purpose is "here is *every* call
site this vendor change will break" cannot be built on a primitive whose native failure mode is
occlusion — nodes hiding behind nodes. **You cannot count what you cannot see**, and that is a
correctness failure, not an aesthetic one. Occlusion making "every affected call site is shown"
unprovable is the entire reason a spatial view of this graph would exist, and it is also the reason
it is declined. There is no secondary reason; if occlusion did not apply, this section would not.

(A canvas also has no DOM — no keyboard navigation, no `Ctrl-F` — and costs roughly 600KB of
`three` on every page load. Those count against it too, but they are costs, not the argument.)

The full four-count case is in
`docs/superpowers/plans/2026-08-05-sync-console-design-system.md`, "Where 3D earns its place, if
anywhere". Read it before reopening this, so the reopening argues with the actual case rather than
a memory of it.

## What retires this decision

**A spatial fact enters the data.** Not more rows, not more vendors, not a bigger graph — a
coordinate: something in the API Dependency Graph that a third axis would represent rather than
fabricate. Nothing on the current roadmap produces one. Until it does, a 3D layout of this graph
is decoration wearing the graph's colours, and decoration is exactly what a console built to stop
confident wrong verdicts cannot render.

If a future need is spatial in a different sense — "which call sites does this one vendor change
touch" — the answer already chosen for that question is a **layered bipartite diagram in SVG**:
DOM nodes, keyboard-navigable, text-searchable, both axes bound to something the graph actually
holds. That is a 2D view and belongs beside the fleet screen, not here.

## If you are reading this wondering whether something got skipped

Nothing did. This is not the placeholder it used to be. "Not built yet" and "declined on the
merits, for now" are different claims, and this file is the second one. If the condition above is
met, build the view and delete this file's argument, not its packages.
