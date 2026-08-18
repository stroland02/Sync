# Owner UI decisions, 2026-08-18 — twelve answers, and what each one settles

Asked as multiple choice so nothing here is a coordinator's guess. **Each answer below is the owner's
selection; the consequence beneath it is mine and is reversible.**

## Structure

**1. First run shows the full console with empty states.** Sidebar and every page visible before a
workspace exists, each saying what it would show. *Consequence:* every screen needs a real
no-workspace state — this is not a gate on the app, it is a state of it.

**2. The Overview leads with fact tiles beside the dependency graph.** Last indexed, call sites,
vendors, bindings by rung, open findings; graph to the right. Findings below. *Consequence:* the
graph panel is above the fold on the first screen, so it is not optional.

**3. The workflow reply box is free text that resumes the run**, exactly as the reference draws it.
*Consequence:* it needs `M10`'s resume-on-review-comment wired, not just rendered.

**4. Long lists are dense tables with a detail drawer.** Click a row, the drawer opens, you keep your
place. *Consequence:* one table component and one drawer, shared across findings, call sites,
bindings, runs.

## Visual

**5. Colour is rich — vocabularies, accents, and data visualisation.** *Consequence, and this is the
one to hold carefully:* a chart may use a multi-hue series for **findings by kind** because those are
categories. **It may not use a red-to-green ramp**, because that reintroduces the good-versus-bad
axis this console refuses. Categorical palettes yes; sequential-severity palettes no.

**6. Vendor logos are shown, fetched.** Small, for identification. *Consequence:* this reverses a
lane's refusal, which was reasoned but is now overruled by the owner. Fetch from a well-known
endpoint, degrade to a monogram when there is none, never redraw a mark.

**7. Density is dense — more on screen.** Tight rows, small type, minimal padding, no page headers.
*Consequence:* `DESIGN.md`'s spacing tokens tighten, and every change carries its contrast arithmetic
against the 5.05:1 floor as usual.

**8. The indexing canvas draws the file tree with edges out to vendors.** *Consequence:* it is framed
as *your codebase*, not as Sync's model of it — `src/api/billing.ts ──▶ stripe`. This is a different
build from the schema-visualiser shape and closer to what a reader already understands.

## Navigation and content

**9. The sidebar lists workspaces, and the current one expands to show its pages.** Orca's nested
disclosure. *Consequence:* this is compatible with `M0-W332` — there is still one set of pages, they
just live under the workspace that owns them. **Workspace creation is a `+` in that rail.**

**10. About covers the glossary and how the pipeline works** — index, signal, detect, remediate,
verify; what each stage reads and writes. *Consequence:* bounded. Not the gates, not the refusals,
not the quickstart.

**11. Empty states show the shape the screen would take** — a greyed skeleton with the reason
overlaid. *Consequence:* this is the strongest possible form of absence-versus-zero, because the
reader sees what is missing rather than being told. **The reason text stays exact:** *telemetry never
attached* is not *no data*.

**12. If only one screen is flawless on Wednesday, it is the solution workflow.** *Consequence:* Lane
B's ordering is confirmed — routes and sidebar first because they block everything, then the
workflow, and the workflow gets whatever time is left rather than being traded away.

## What did not change

The three refusals stand: no confidence scalar on the workflow, no health tile on the Overview, no
status dots in the rail. Answer 5 makes colour richer and answer 6 overturns a lane's judgement, but
neither touches what the console is allowed to claim.

## Round two — eight more, 2026-08-18

**13. The dependency graph draws everything, with pan, zoom and a minimap.** *Consequence:* it needs
a real canvas with viewport culling, not a static SVG. This is the largest single build on the list
and it sits above the fold on the first screen, so it is not deferrable.

**14. The Activity tab shows node summaries that expand to their tool calls.** One line per graph
node with its outcome; click to open the detail beneath. *Consequence:* scannable first, complete on
demand — and the expansion is where the evidence lives.

**15. Findings group by kind, breaking first**, under a triage header carrying each count. *That is
the advisor shape*, applied to the thing this product exists to surface.

**16. Creating a workspace accepts a local path or a git URL.** *Consequence:* Sync clones when given
a URL — which is the demo case, pointing it at something public on the spot.

**17. Settings uses a left sub-nav, one group at a time.** Codebases, Pull requests, Adapters,
Connection, About.

**18. Signals leads with attached integrations grouped by role** — vendor, signal source, human
surface — which is what the screen is already built around, so this confirms rather than changes it.

**19. Indexing finishes on the canvas**, not the Overview. *Consequence, and it raises the canvas's
priority again:* the file tree with its vendor edges is the payoff screen for the one-command
install. **The `is this real` moment lands here.**

**20. Where the mock conflicts with any of these answers, the answer wins.**

## The authority order, now settled end to end

`M0-W325` raised the mock to primary for everything it draws. **Answer 20 puts these decisions above
it.** So, highest first:

1. **The owner's decisions in this document.**
2. **The specification** for the hierarchy (`console-hierarchy.md`), and `CLAUDE.md` for what may be
   claimed. *Neither is overridden by anything above.*
3. **The mock**, for layout — grid tracks, gaps, adjacency, composition.
4. **Everything else.**

**Recorded conflicts to resolve the mock's way losing:** it draws a Fleet root (answer: workspace-
scoped) and page headers (answer: removed). A lane finding a new conflict records it here rather than
resolving it silently.
