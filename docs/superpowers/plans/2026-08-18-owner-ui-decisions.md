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
