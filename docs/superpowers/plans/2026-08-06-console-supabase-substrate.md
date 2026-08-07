# Console Supabase Substrate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the console's presentation layer on Supabase's vendored component library, per `specs/2026-08-06-sync-console-supabase-substrate-design.md`.

**Architecture:** Vendor `packages/ui` from `supabase/supabase` (Apache-2.0) nearly verbatim into `web/src/vendor/supabase/`; swap the theme contract in `DESIGN.md` and its token guard together; rebuild the chassis as a 40px icon rail plus contextual sidebar; then recompose the nine levels one work item at a time, each preceded by a field-to-slot mapping table and gated by an old-screen/new-screen completeness walk.

**Tech Stack:** React 19, Vite 8, Tailwind 4 (`@theme` in CSS), React Router 8, radix-ui, vitest/jsdom, Python 3.12 + pytest for the cross-language guards.

## Global Constraints

- **Branch:** every worker branches off `console-identity`, pushes its own branch, never opens a PR, never pushes `main`. Coordinator merges.
- **Gate on every task, before reporting done:** `uv run pytest tests/ -q -n0` from the worktree root, then `npm run build`, `npm run lint`, `npm test` from `web/`. Local gate is the authority (B112).
- **`tests/test_console_honesty_sentences.py` must stay green.** A red run means a protected sentence was deleted; restore it, never reword it.
- **The data seam does not move** (spec §10): `web/src/api/client.ts`, `api/queries.ts`, `api/types.ts`, `lib/format.ts`, `components/states.tsx`, `components/status.tsx`, `components/provenance.tsx`, `features/fleet/cardinality.tsx`, `features/detectors/rung-series.ts`. A task finding itself editing these has left its brief — stop and escalate.
- **Vendored files under `web/src/vendor/supabase/` receive only:** import-path fixes, Next `Link`/router → React Router, i18n and feature-flag stripping, TS config accommodations. No restyling inside vendored files, ever.
- **No composite score, health figure, traffic light, green dot, liveness pulse, count-up.** Dark-only. No snapshots in vitest; behavior only. Every new test proven RED first.
- **Python:** always `python`, never `python3`; `encoding="utf-8"` on every `read_text`/`write_text`/`open`/`subprocess.run(text=True)`.
- **Commits:** Conventional Commits with the work-item number in the subject (`feat: M7-W1xx …`). Take the next number from `docs/superpowers/WORKLOG.md`, add the row before starting.
- Every `set_viewport` in Chrome measurement is paired with `clear_viewport` before the task ends.

---

### Task 1: Amend the records so the rules match the rulings

**Files:**
- Modify: `.claude/rules/interface-originality.md`
- Modify: `docs/superpowers/references/direction/NOTES.md`
- Modify: `docs/superpowers/plans/2026-08-06-m7-console-as-product.md`

**Interfaces:**
- Produces: a rule tree under which Tasks 2–6 are legal. No code.

- [ ] **Step 1: Add the Supabase carve-out to `interface-originality.md`**

Append this section verbatim before "## The reason this is not merely legal caution":

```markdown
## The Supabase carve-out (owner-authorized, 2026-08-06)

`specs/2026-08-06-sync-console-supabase-substrate-design.md` records the owner's ruling: Supabase's
component code (`github.com/supabase/supabase`, Apache-2.0) is adopted at code level as the
console's foundation — vendored nearly verbatim under `web/src/vendor/supabase/`, with attribution
in `web/NOTICE`. For this one source, "a component's appearance" and "a component built by looking
at a screenshot" are no longer refusals; the code itself is taken.

The carve-out does not touch the rest of this rule. Identity elements stay excluded — the Supabase
wordmark, logo, identifying iconography, marketing and product copy. Every other reference is
governed exactly as before. And no vendored component may assert a claim our data cannot support:
a slot for a confidence score renders the rung instead, per the spec's section 6.
```

- [ ] **Step 2: Amend direction note 6 with the reversal**

Append to `references/direction/NOTES.md`, at the end of entry 6's section:

```markdown
### Reversed by the owner, 2026-08-06

Entry 6 chose one sidebar at two widths and the chassis (M7-W160) built it. Choosing the Supabase
substrate, the owner ruled for Supabase's arrangement instead: a 40px icon rail for areas plus a
contextual sidebar for the level you are inside. The mechanical test in this entry — an icon must
not move vertically on collapse — now applies within the rail alone. The entry above stays as
written because it records what the screenshots showed; this amendment records that the target
changed. `specs/2026-08-06-sync-console-supabase-substrate-design.md` §4 carries the new shape.
```

- [ ] **Step 3: Point the M7 plan at the spec**

In `plans/2026-08-06-m7-console-as-product.md`, insert directly under the `**Status:**` line:

```markdown
**Amended 2026-08-06 by `specs/2026-08-06-sync-console-supabase-substrate-design.md` (M7-W165):**
Phase 1's "no component is copied" is superseded — Supabase's components are vendored wholesale
under an owner-authorized carve-out. Phase 2's chassis is rebuilt two-tier. Phases 4–5 continue on
the vendored substrate; each remaining level port follows the spec's §10 mapping-table gate.
```

- [ ] **Step 4: Gate and commit**

Run the full gate (Global Constraints). All green — docs only, but the gate catches an accidentally
touched file.

```bash
git add .claude/rules/interface-originality.md docs/superpowers/references/direction/NOTES.md docs/superpowers/plans/2026-08-06-m7-console-as-product.md docs/superpowers/WORKLOG.md
git commit -m "docs: M7-W1xx the records match the substrate rulings"
```

---

### Task 2: Vendor the Supabase component library, with the NOTICE guard

**Files:**
- Create: `web/src/vendor/supabase/ui/*` (component set below)
- Create: `web/NOTICE`
- Create: `web/src/vendor/supabase/README.md`
- Test: `tests/test_console_vendor_notice.py`

**Interfaces:**
- Produces: importable components at `@/vendor/supabase/ui/<name>` — at minimum `button`, `badge`,
  `table`, `dropdown-menu`, `sheet`, `dialog`, `tabs`, `command`, `sidebar`, `tooltip`, `input`,
  `select`, `separator`, `skeleton`, `breadcrumb`, `scroll-area`, `popover`, `card`. Later tasks
  import these instead of `@/components/ui/*`.

- [ ] **Step 1: Write the failing NOTICE guard**

```python
"""Every vendored Supabase file is attributed, and the attribution is complete.

Grain: one NOTICE entry per file under web/src/vendor/supabase/.
"""
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"
VENDOR = WEB / "src" / "vendor" / "supabase"
NOTICE = WEB / "NOTICE"


def vendored_files() -> list[Path]:
    return [p for p in VENDOR.rglob("*") if p.suffix in {".ts", ".tsx"}]


def test_vendor_directory_exists_and_is_nonempty():
    assert VENDOR.is_dir(), "web/src/vendor/supabase/ missing"
    assert vendored_files(), "vendor directory holds no TypeScript"


def test_notice_names_every_vendored_file():
    notice = NOTICE.read_text(encoding="utf-8")
    assert "Apache License" in notice and "supabase/supabase" in notice
    missing = [
        str(rel)
        for p in vendored_files()
        if (rel := p.relative_to(WEB).as_posix()) not in notice
    ]
    assert not missing, f"vendored but not in NOTICE: {missing}"


def test_notice_pins_the_source_commit():
    import re
    notice = NOTICE.read_text(encoding="utf-8")
    assert re.search(r"pinned at commit [0-9a-f]{7,40}", notice), "NOTICE names no pinned SHA"
```

- [ ] **Step 2: Run it, watch it fail**

Run: `uv run pytest tests/test_console_vendor_notice.py -q`
Expected: FAIL — `web/src/vendor/supabase/ missing`.

- [ ] **Step 3: Sparse-clone Supabase, pinned**

Pin at `6ac0316` — the commit M7-W159's mechanism note cites, so its file-and-line citations stay
valid against what we vendor. Clone outside the repository:

```bash
SCRATCH="$(mktemp -d)"; cd "$SCRATCH"
git clone --depth 1 --filter=blob:none --sparse https://github.com/supabase/supabase.git
cd supabase
git sparse-checkout set packages/ui packages/ui-patterns apps/studio
git fetch --depth 1 origin 6ac0316 && git checkout 6ac0316
```

If `6ac0316` is unreachable shallow, fetch it explicitly (`git fetch origin 6ac0316 --depth 1`); do
not silently substitute HEAD — a different commit invalidates the note's citations, and the NOTICE
must state what was actually taken.

- [ ] **Step 4: Copy the component set, adapt imports only**

For each component named in **Interfaces**, copy its source from `packages/ui` (their shadcn-style
component files) into `web/src/vendor/supabase/ui/<name>.tsx`, preserving internal structure. Then,
in vendored files only:

- Rewrite their internal utility imports to `@/lib/utils` (`cn` already exists there).
- Rewrite radix imports to match our monolith package (`radix-ui`) if their per-package imports
  (`@radix-ui/react-*`) fail to resolve; prefer adding nothing to `package.json` — every radix
  primitive ships inside `radix-ui@1.6.7`.
- Swap any Next `Link`/`useRouter` for `react-router` equivalents.
- Delete i18n and feature-flag imports and inline their fallback strings.
- Add one header line to each file: `// Vendored from supabase/supabase (Apache-2.0), packages/ui, commit 6ac0316. See web/NOTICE.`

Also copy their theme CSS custom-property block (the dark values) into
`web/src/vendor/supabase/theme.css` untouched — Task 3 consumes it; nothing imports it yet.

`web/src/vendor/supabase/README.md` states the editing rule in three lines: what edits are allowed
(the Global Constraints list), that restyling happens outside this directory, and where NOTICE is.

- [ ] **Step 5: Write `web/NOTICE`**

```text
This directory vendors components from supabase/supabase
(https://github.com/supabase/supabase), pinned at commit 6ac0316, under the
Apache License 2.0. Original copyright Supabase Inc.

Vendored files:
  src/vendor/supabase/ui/button.tsx
  src/vendor/supabase/ui/badge.tsx
  ... (one line per vendored file, exact relative paths)
  src/vendor/supabase/theme.css
```

List every file actually copied; the guard fails on any omission.

- [ ] **Step 6: Run the guard, watch it pass; run the full gate**

Run: `uv run pytest tests/test_console_vendor_notice.py -q` → PASS.
Then the full Global Constraints gate. `npm run build` will surface unresolved imports in vendored
files — fix per Step 4's allowed edits only. Nothing renders the vendored components yet; the build
proving they compile is this task's deliverable.

- [ ] **Step 7: Commit**

```bash
git add web/src/vendor/ web/NOTICE tests/test_console_vendor_notice.py docs/superpowers/WORKLOG.md
git commit -m "feat: M7-W1xx vendor the Supabase component library, attributed and guarded"
```

---

### Task 3: Swap the theme contract — `DESIGN.md`, tokens, and guard move together

**Files:**
- Modify: `web/src/index.css`
- Modify: `DESIGN.md`
- Modify: `tests/test_console_design_tokens.py`
- Consume: `web/src/vendor/supabase/theme.css` (from Task 2)

**Interfaces:**
- Produces: the token vocabulary every later task styles with — Supabase's color custom properties
  and type/spacing/radius steps, declared in `index.css` `@theme` and documented in `DESIGN.md`.

- [ ] **Step 1: Port the dark theme values into `@theme`**

Replace the color block of `index.css`'s `@theme` with the custom properties from
`theme.css` (dark values only — dark-only stands, owner ruling 2026-08-05). Map their semantic
names onto our existing token names where a one-to-one exists (`--background`, `--foreground`,
`--border`, `--muted`…), and add their additional scale steps under their own names. Keep our
`--text-*` step names but set each to Supabase's ramp values, including their display steps —
this is where the 2.0:1 type-range defect dies.

- [ ] **Step 2: Rewrite `DESIGN.md` as the substrate contract**

Every token that survives Step 1, with its value and its source (`theme.css` name). Keep the
document's existing structure — Color, Type, Space, Elevation — and its rule that a new token is a
decision argued in the file. Replace the superseded Type/Space refusals with the substrate values;
cite spec §3.

- [ ] **Step 3: Measure contrast, record deviations**

For every text-bearing pairing declared in `DESIGN.md`, compute the WCAG ratio (small Node script or
by hand; the existing `DESIGN.md` shows the arithmetic form). Each pairing ≥ 5.05:1 is recorded as
before; each below it gets a named deviation entry with its measured ratio. No silent acceptance.

- [ ] **Step 4: Rewrite the token guard against the new contract, prove it RED**

`tests/test_console_design_tokens.py` currently reads its thresholds out of `DESIGN.md`. Update its
parsing to the rewritten sections, keeping its direction — it fails when a screen adds a color
literal, a raw spacing value, or a token outside the contract. Prove it RED: add a rogue
`color: #ff0000` to any `features/` file, run, watch it fail, revert the rogue value.

Run: `uv run pytest tests/test_console_design_tokens.py -q` → PASS after the revert.

- [ ] **Step 5: Look at the running console**

`npm run dev` (worker's own port, stopped before reporting). Every screen renders with the new
palette; nothing unstyled. State what was observed.

- [ ] **Step 6: Gate and commit**

Full Global Constraints gate.

```bash
git add web/src/index.css DESIGN.md tests/test_console_design_tokens.py docs/superpowers/WORKLOG.md
git commit -m "feat: M7-W1xx the theme contract becomes the Supabase substrate"
```

---

### Task 4: The chassis, two-tier — icon rail plus contextual sidebar

**Files:**
- Modify: `web/src/lib/routes.ts`
- Modify: `web/src/layouts/app-frame.tsx`
- Modify: `web/src/layouts/breadcrumbs.tsx` (only if the rail changes what it receives)
- Test: `web/src/lib/routes.test.tsx` (extend), `web/src/layouts/app-frame.test.tsx` (extend)

**Interfaces:**
- Consumes: the vendored `sidebar`, `tooltip`, `separator` components (Task 2), the theme (Task 3).
- Produces: `RouteEntry` gains `area: Area` and optional `pages: string[]`;
  `type Area = "fleet" | "codebase" | "api-services" | "signals" | "observe" | "remediation"`;
  helper `isActiveMenuItem(entry: {path: string; pages?: string[]}, pathname: string): boolean`.
  Every level port (Tasks 6+) renders inside this frame unchanged.

- [ ] **Step 1: Write the failing tests**

Extend `routes.test.tsx`:

```tsx
import { GRAPH_LEVELS, ROUTES, isActiveMenuItem } from "@/lib/routes"

const AREAS = ["fleet", "codebase", "api-services", "signals", "observe", "remediation"] as const

test("every route carries a declared area", () => {
  for (const r of ROUTES) expect(AREAS).toContain(r.area)
})

test("areas group levels without inventing one", () => {
  // The vocabulary is pinned to the spec by tests/test_console_hierarchy.py;
  // here: no area claims a level outside GRAPH_LEVELS.
  for (const r of ROUTES) expect(GRAPH_LEVELS).toContain(r.level)
})

test("a menu item owning several routes says so in data", () => {
  expect(isActiveMenuItem({ path: "/findings", pages: ["/findings", "/findings/:id"] }, "/findings/42")).toBe(true)
  expect(isActiveMenuItem({ path: "/findings" }, "/signals")).toBe(false)
})
```

Extend `app-frame.test.tsx` (behavioral, no class names):

```tsx
test("the rail names every area exactly once and Settings last", () => {
  render(<AppFrame />, { wrapper: routerWrapper("/") })
  const nav = screen.getByRole("navigation", { name: /areas/i })
  const items = within(nav).getAllByRole("link").map((el) => el.getAttribute("aria-label"))
  expect(items[items.length - 1]).toMatch(/settings/i)
  expect(new Set(items).size).toBe(items.length)
})

test("a collapsed rail item keeps its accessible name", () => {
  render(<AppFrame />, { wrapper: routerWrapper("/") })
  expect(screen.getByRole("link", { name: /fleet/i })).toBeInTheDocument()
})
```

- [ ] **Step 2: Run them, watch them fail**

Run: `cd web && npx vitest run src/lib/routes.test.tsx src/layouts/app-frame.test.tsx`
Expected: FAIL — `area` and `isActiveMenuItem` do not exist.

- [ ] **Step 3: Extend the registry**

In `lib/routes.ts`: add the `Area` type and `area` to `RouteEntry` per the spec §4 table (Fleet →
`fleet`; Codebase → `codebase`; API Services → `api-services`; Signals → `signals`; Binding surface
and Errors & Incidents → `observe`; Finding, Solution Workflow, Pull Request → `remediation`).
Add `pages` where a menu item owns a detail route. Add:

```ts
export function isActiveMenuItem(
  entry: { path: string; pages?: string[] },
  pathname: string,
): boolean {
  const owned = entry.pages ?? [entry.path]
  return owned.some((p) =>
    p.includes(":") ? matchPath(p, pathname) !== null : pathname === p || pathname.startsWith(p + "/"),
  )
}
```

The registry gains fields; its shape does not change — `tests/test_console_hierarchy.py` and the
route-shape pytest stay green untouched, and if either goes red the change was wrong, not the test.

- [ ] **Step 4: Rebuild `app-frame.tsx` on the vendored sidebar**

Structure, transcribed from Studio's arrangement (M7-W159 §1) without its machinery:

- A fixed 40px icon rail (`nav` with `aria-label="Areas"`): one icon per area from the spec table,
  Settings pinned last, each a `Link` wrapped in the vendored `tooltip` carrying the area name;
  active area marked by `isActiveMenuItem` over the area's routes.
- A contextual sidebar beside it: the active area's name as its heading, the area's destinations
  grouped under small-caps letterspaced labels, each row icon-plus-label, active row on a filled
  surface. Built on the vendored `sidebar` primitive in fixed-width mode — no resizable panel
  group, no deferred mount (the note records why Studio needs them and we do not).
- The content region: header (breadcrumbs unchanged), `main`, footer slot — as today.

- [ ] **Step 5: Run the tests, watch them pass; look at every route**

Run: `cd web && npx vitest run` → PASS, including the pre-existing app-frame and routes tests.
`npm run dev`: walk all nine levels; every route reachable from the rail; sidebar heading matches
the area; no icon moves vertically within the rail across navigation. Stop the server.

- [ ] **Step 6: Measure**

Chrome at 1440×900 and 1280×800: type range on `/` (display step now renders), frame ratio, rows
above the fold at `--scale 10000`. Record before/after in the work item's report. `clear_viewport`.

- [ ] **Step 7: Gate and commit**

```bash
git add web/src/lib/routes.ts web/src/lib/routes.test.tsx web/src/layouts/ docs/superpowers/WORKLOG.md
git commit -m "feat: M7-W1xx the chassis goes two-tier on the vendored sidebar"
```

---

### Task 5: The Fleet port — the pattern every level follows

**Files:**
- Modify: `web/src/features/fleet/fleet-page.tsx`, `repositories-table.tsx`, `runs-table.tsx`,
  `corpus-summary.tsx`, `detectors-summary.tsx`, `vendor-distribution.tsx`
- Test: existing fleet vitest files (extend where a derivation changes; expect none)
- Brief first: `docs/superpowers/briefs/2026-08-0X-substrate-fleet.md`

**Interfaces:**
- Consumes: vendored `table`, `badge`, `card`, `skeleton`, `breadcrumb`, `sheet`; `fact-tile`,
  `metric-panel`, `footer-bar` (existing, restyled onto vendored primitives here if trivial,
  otherwise kept as-is this task).
- Produces: the port pattern — mapping table, recomposition, completeness walk — that Task 6
  replicates per level.

- [ ] **Step 1: Write the mapping table into the brief (spec §10 gate)**

Open `fleet-page.tsx` and each child component; list every rendered field in a table — field on the
left, target slot on the right:

```markdown
| Field rendered today | Substrate slot |
|---|---|
| repository name (link) | table identifying column, link |
| last indexed timestamp | fact tile `LAST INDEXED` |
| index coverage | fact tile with bounded-count floor sentence intact |
| open findings count | metric panel value, evidence rows beneath |
| run outcome + abandon_reason | table column, closed-vocabulary badge + word |
| rung distribution | rung-composition chart, unchanged, inside a metric panel |
| … every remaining field, exhaustively … | … |
```

A field with no slot is resolved in the brief — new slot or recorded ruling — before Step 2.

- [ ] **Step 2: Recompose onto the vendored components**

Tables take Studio's anatomy: uppercase letterspaced headers, identifying column as a link, `⋮`
overflow at row end, footer bar with pagination/page-size/record-count. Overview top takes the
fact-tile grid; each headline count becomes a metric panel — value at display size above its
evidence. Empty states wrap the existing `states.tsx` sentences in the vendored empty-state
pattern. All imports move from `@/components/ui/*` to `@/vendor/supabase/ui/*` for this feature.

- [ ] **Step 3: Run the vitest suite**

Run: `cd web && npx vitest run src/features/fleet`
Expected: PASS unchanged — these tests assert behavior, not markup. A red test means behavior was
lost; fix the port, not the test.

- [ ] **Step 4: The completeness walk**

`uv run python scripts/seed_console.py`, then walk the old screen (git stash or the pre-port
commit checked out in a scratch worktree) and the new screen against the same seed. State in the
report: every fact the old screen asserted is asserted by the new one, or the exception's ruling
is in the plan ledger. Honesty test green.

- [ ] **Step 5: Measure, gate, commit**

Chrome before/after per Task 4 Step 6. Full gate.

```bash
git add web/src/features/fleet docs/superpowers/briefs/ docs/superpowers/WORKLOG.md
git commit -m "feat: M7-W1xx Fleet recomposed on the substrate"
```

---

### Task 6: The remaining eight levels, one work item each

**Files:** per level, its `features/<level>/` directory; a brief per level.

**Interfaces:**
- Consumes: Task 5's pattern, verbatim.

- [ ] **Step 1–8: For each of** Codebase, API Services, Signals, Binding surface,
  Errors & Incidents, Finding, Solution Workflow, Pull Request — in that order:

The coordinator writes the level's brief (mapping table per Task 5 Step 1, plus the level's
specifics from the M7 plan's Phase 4–5 sections: the workflow narrative for Solution Workflow, the
single-binding node card for Binding surface, the faceted explorer for Errors & Incidents and
Signals, the provenance-chip catalogue for Signals' integrations grid). Dispatch a worker; the
worker follows Task 5's steps 2–5 exactly; coordinator reviews against the brief, merges, gates,
restarts 5173, says so.

Detail drawers (vendored `sheet`, URL-addressable) arrive with the level that owns the detail —
Finding and Binding surface first.

- [ ] **Final step: fast-forward `main`**

After the last level lands and the gate is green:
`git merge-base --is-ancestor origin/main console-identity` then
`git push origin <sha>:refs/heads/main`.

---

## Self-review (run at write time)

- **Spec coverage:** §1 stance → Task 2 README + constraints; §2 manifest → Task 2; §3 theme →
  Task 3; §4 chassis → Task 4; §5 ports → Tasks 5–6; §6 immovables → Global Constraints; §7
  records → Task 1; §8 machinery → Global Constraints + Task 6 process; §9 verification →
  per-task gates; §10 seam and mapping → Global Constraints + Task 5 Steps 1 and 4. No gap found.
- **Placeholders:** the mapping table in Task 5 Step 1 is deliberately produced *by* the task from
  named files; the component list in Task 2 is explicit. The `M7-W1xx` in commit subjects is the
  repo's own numbering rule (take the next number at dispatch), not a placeholder.
- **Type consistency:** `Area` union, `isActiveMenuItem` signature, and vendor import paths named
  identically in Tasks 2, 4, 5.
