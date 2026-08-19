# Reference read: how open-source draws a large codebase (2026-08-18)

The owner's report: the dependency graph is unreadable on a real codebase — everything is drawn
at once, and zoom stops before anything becomes legible. Surveyed what open source does about
exactly this, licenses stated, under `interface-originality.md` (ideas transfer, renderings do
not).

| Project | Approach | License | Verdict |
|---|---|---|---|
| `githubocto/repo-visualizer` | circle-packs a repository, area by file size | MIT | **STEAL-THE-IDEA** — *hierarchical aggregation*: a directory is one shape until you go into it. Its circle packing suits file *size*; ours must show edges out to operations, which packing hides |
| Sourcetrail (archived) | graph + code, **expand-on-demand** from one focused node | GPL-3 | **STEAL-THE-IDEA, never the code** — GPL is incompatible with Apache-2.0 distribution. Its rule is the one that matters: never draw the whole graph, draw a neighbourhood and let the reader widen it |
| xyflow / React Flow | node canvas with in-canvas `Controls`, `MiniMap`, `Panel` | MIT | **CONVENTION** — controls belong *inside* the canvas, floating over it, not in a toolbar above. That is the owner's own instruction, and it is the standard shape |
| Cytoscape.js + fcose | force/compound layouts, collapsible compound nodes | MIT | **SKIP as a dependency** — a graph engine to lay out a file tree we already lay out; its *collapsible compound node* is the idea, and it is the same idea as Sourcetrail's |
| elkjs | layered layout | EPL-2.0 | **SKIP** — weak-copyleft, and a 1MB layout engine for a tree with a known shape |
| d3-hierarchy | tidy tree / treemap / pack primitives | ISC | Available if a second view is ever wanted; the current layout needs none of it |

## What every one of them does that we did not

**Level of detail.** None draws every leaf of a large repository at once. They aggregate to a
container and expand on demand — a directory is a node until you open it. Ours drew all 165
call sites and every folder between them, then fitted the result into 576 pixels.

**Absolute zoom, not relative.** Ours capped zoom at `fit / 4`, which on a small graph is
plenty and on a large one is still illegible: the cap scaled *with the problem*. A zoom limit
has to be expressed in the units a reader sees — pixels per row — so it means the same thing on
any codebase.

**Controls in the canvas.** Floating over the picture, bottom-left or top-right, with the
minimap in the opposite corner. A toolbar above the frame reads as page furniture rather than
as part of the map.

## What was built from this (`CI-W480`)

- `zoomViewport` takes a legibility floor and ceiling in pixels rather than a multiple of fit,
  so zoom always reaches a readable scale whatever the codebase's size.
- Directories collapse, and a large tree **opens collapsed past its first level**, with each
  collapsed folder carrying the count it stands for and expanding on click. Bindings re-attach
  to the nearest visible ancestor, so a collapsed folder's edges are its subtree's edges rather
  than disappearing with it.
- Controls and the minimap float inside the canvas card, over the picture.
