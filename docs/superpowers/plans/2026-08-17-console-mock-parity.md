# Console Mock Parity & Honest Motion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring every console screen to the composition quality of the owner's mock (`docs/console-mock/`), make the workflow route a live-feeling trajectory view without asserting liveness the data cannot back, and leave guards behind so the console cannot silently drift flat again.

**Architecture:** Foundation-first. Phase 0 makes the ledgers true and installs the measurement loop and a raw-utility guard. Phase 1 puts every screen on the shared chassis (one `DetailGrid`, `PageHeader` everywhere, tokens only, no fixture data rendered as fact). Phase 2 closes small composition gaps. Phase 3 rebuilds the workflow route to mock screen 07 with an activity timeline, evidence disclosures, ticking evidence-age, and idle-node recession. Phase 4 lands the never-built destinations and the closing measured walk.

**Tech Stack:** React 18 + Vite + TypeScript (`web/`), vitest + RTL (`npm test` from `web/`), vendored Supabase components (Apache-2.0, attributed in `web/NOTICE`), pytest guards in `tests/`, Chrome measurement via the `superpowers-chrome:browsing` skill.

**Spec:** `docs/superpowers/specs/2026-08-17-sync-console-mock-parity-design.md`

## Global Constraints

- **Integration branch: `console-parity`.** Workers branch from it, gate on it, push their own branch; the coordinator merges. A worker never opens a PR and never pushes `main`.
- **Work item register:** before starting a task, take the next free number from **Lane B's allocated block W260-W279** (`docs/superpowers/orchestration/2026-08-17-lane-charters.md`); the milestone prefix for this plan is `M14`. Add the row before the first commit; carry the identifier on every commit for the task. (Amended 2026-08-17: the plan originally said "continue from W225", which collided with numbers other lanes had landed; W228-W233 were renumbered to W260-W265.)
- Python is `python`, never `python3`. Packages via `uv` only. Postgres is on port 5433.
- **Always pass `encoding="utf-8"`** to every `read_text`, `write_text`, `open`, and `subprocess.run(..., text=True)`.
- `DESIGN.md` is the token authority. No new token, spacing value, or type step without an argued amendment there. Contrast floor 5.05:1.
- **Honesty rules bind every task:** no composite score, health figure, traffic light, green dot, liveness pulse, or count-up. The 24 protected sentences (`plans/2026-08-05-sync-console-architecture.md:102-207`) may be restyled or re-placed, never deleted, shortened, or collapsed behind a disclosure. Every diff is re-read for a deleted qualification before commit.
- **Test discipline:** vitest covers classification, derivation, and structural invariants — never class names, never snapshots. Every new test is shown RED against a deliberately broken subject before it is trusted. Rendered-pixel claims are measured in Chrome and written into `DESIGN.md`, not asserted in vitest.
- **Open-source adoption (spec ruling 4):** copy from permissively licensed sources openly — license checked first, attribution line added to `web/NOTICE`, adapted to our tokens. Never obscure origin. Sources with unverifiable licenses are not copied from.
- **Gates before any task reports done:** `cd web && npm run build && npm run lint && npm test`, and `uv run pytest tests/ -q` when Python files changed. Say which ran.
- **Dev loop:** per `.claude/rules/console-dev-loop.md`. A worker's dev server runs on a free port and is stopped before reporting. Every `set_viewport` is paired with `clear_viewport`.
- **Executing this plan:** decide and continue per `.claude/rules/autonomous-development.md`; rulings go in the SDD ledger at the bottom of this file.

---

## Phase 0 — truth and guards

### Task 1: Make the ledgers true

**Files:**
- Modify: `docs/superpowers/BACKLOG.md` (the plan-status table rows for `2026-08-08-console-mock-to-build.md` and `2026-08-08-console-direction-parity.md`, and the M13 row)
- Modify: `docs/superpowers/plans/2026-08-08-console-mock-to-build.md` (status note at top)
- Modify: `docs/superpowers/plans/2026-08-16-sync-m13-dynamic-visuals-and-telemetry.md` (status note at top)

**Interfaces:**
- Produces: ledger rows later tasks cite. No code.

Documentation task — no test cycle. Verification is re-reading the diff against the audit facts below, all verified against the tree on 2026-08-17:

- `2026-08-08-console-mock-to-build.md`: Task 1 (mock gap report) never run — `docs/superpowers/reports/2026-08-08-console-mock-gaps.md` does not exist; Task 3 (shared drawer) not built; Task 5 (`/settings`) not built — no `web/src/features/settings/`; Task 6 (palette test) not built — no `command-palette.test.tsx`. Task 2's frontend half landed (`change-units-table.tsx`).
- `BACKLOG.md` currently marks that plan "Landed (Phases 1-6)" — true only of the appended phase block, not the six numbered tasks.

- [ ] **Step 1:** Edit the `BACKLOG.md` row for `console-mock-to-build` to read: "Partially landed — appended Phases 1-6 only; Tasks 1, 3, 5, 6 open, absorbed by `2026-08-17-console-mock-parity.md`". Edit the `direction-parity` row to note its checkboxes predate the reconciliation and the tree is the authority. Edit the M13 row to: "Superseded in phasing by `2026-08-17-console-mock-parity.md` per spec ruling 2 (no pulse) and 3 (Remotion deferred)".
- [ ] **Step 2:** Add a status note under the header of each of the two plan files, dated 2026-08-17, stating what the tree shows built and pointing at this plan for the remainder.
- [ ] **Step 3:** Re-read the diff: every claim must match the audit facts above; no protected sentence touched.
- [ ] **Step 4:** Commit: `docs: M14-W<n> reconcile console plan ledgers with the tree`

### Task 2: Raw-utility guard with a shrinking baseline

**Files:**
- Create: `tests/test_console_raw_utilities.py`
- Create: `tests/console_raw_utilities_baseline.txt`
- Test: the file is its own test.

**Interfaces:**
- Consumes: `web/src/features/**/*.tsx` sources.
- Produces: `console_raw_utilities_baseline.txt`, one `relative/path.tsx<TAB>utility` pair per line, sorted, UTF-8. Task 7 shrinks it to empty; the guard fails on any pair not in the baseline.

The patterns this guard hunts, chosen from the 2026-08-17 audit (37 occurrences in 14 files). `gap-8` is deliberately exempt — `DESIGN.md:657-685` names it as the unnamed between-panel gap.

- [ ] **Step 1: Write the failing test**

```python
"""Raw Tailwind utilities inside ``web/src/features`` — a shrinking baseline.

``DESIGN.md`` records the decision: four spacing tokens, two radius tokens, seven
type steps, and colour only through tokens. A raw utility inside ``features/``
duplicates one of them under a different name, or asserts a judgement colour the
surface rules forbid. The baseline file holds the violations that existed when the
guard landed; it only ever shrinks. A pair not in the baseline fails immediately.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_FEATURES = _REPO_ROOT / "web" / "src" / "features"
_BASELINE = Path(__file__).resolve().parent / "console_raw_utilities_baseline.txt"

# Each alternative is a raw spelling with a token answer. ``gap-8`` is exempt by
# DESIGN.md's own text; icon ``size-*`` is geometry, not spacing, and is not hunted.
_RAW = re.compile(
    r"(?<![-\w:])("
    r"text-(?:xs|sm|base|lg|xl|2xl|3xl|4xl)"          # type steps exist for these
    r"|rounded(?:-(?:sm|md|lg|xl|2xl|full))?(?![-\w])"  # radius-control / radius-surface
    r"|(?:p|px|py|m|mx|my|gap)-(?:0\.5|1|1\.5|2|2\.5|3|4|5|6)(?![-\w.])"
    r"|(?:bg|text|border)-(?:emerald|amber|red|green|blue|yellow|orange|rose|sky|"
    r"slate|zinc|gray|stone|neutral)-\d{2,3}(?:/\d{1,3})?"
    r")"
)


def _current_pairs() -> set[str]:
    pairs: set[str] = set()
    for path in sorted(_FEATURES.rglob("*.tsx")):
        text = path.read_text(encoding="utf-8")
        for match in _RAW.finditer(text):
            rel = path.relative_to(_REPO_ROOT / "web").as_posix()
            pairs.add(f"{rel}\t{match.group(1)}")
    return pairs


def test_features_add_no_raw_utilities() -> None:
    assert _FEATURES.is_dir(), "features directory moved; update the guard"
    baseline = set(
        line
        for line in _BASELINE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    new = _current_pairs() - baseline
    assert not new, (
        "Raw Tailwind utilities not in the baseline (use the token; "
        "DESIGN.md is the authority):\n" + "\n".join(sorted(new))
    )
```

- [ ] **Step 2: Run with an empty baseline file to see it fail on the real tree**

Create `tests/console_raw_utilities_baseline.txt` empty, then:
Run: `uv run pytest tests/test_console_raw_utilities.py -q`
Expected: FAIL listing the current violations (the audit counted 37; the exact set the regex finds is the truth — record it).

- [ ] **Step 3: Seed the baseline from the failure output**

Write every reported pair into `tests/console_raw_utilities_baseline.txt`, one per line, sorted.

- [ ] **Step 4: Run to verify it passes, then prove it still bites**

Run: `uv run pytest tests/test_console_raw_utilities.py -q` → PASS.
Add `className="text-sm"` to any features file, run again → FAIL naming the new pair. Revert the deliberate break, run once more → PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_console_raw_utilities.py tests/console_raw_utilities_baseline.txt
git commit -m "test: M14-W<n> raw-utility guard over features/ with a shrinking baseline"
```

### Task 3: Baseline measured walk — the mock gap report

**Files:**
- Create: `docs/superpowers/reports/2026-08-17-console-mock-gaps.md`

**Interfaces:**
- Consumes: the running console (dev loop), `docs/console-mock/screens/*.png`.
- Produces: the per-screen measurement table Phase 2–4 tasks cite, and the numbers the closing walk (Task 15) is compared against.

This is mock-to-build Task 1, five days late. No code changes. Use the `superpowers-chrome:browsing` skill.

- [ ] **Step 1: Start the loop** per `.claude/rules/console-dev-loop.md`: `SYNC_API_RELOAD=true uv run python -m sync.api` (8787), `uv run python scripts/seed_console.py`, `cd web && npm run dev` on a free worker port (never 5173 — that is the owner's).
- [ ] **Step 2: Set the mock's capture conditions** in the automation browser: `set_viewport` 1440×900, `deviceScaleFactor: 1`.
- [ ] **Step 3: For each of the nine routes** (`/`, `/repositories/:repoId`, `/vendors/:vendorId`, `/repositories/:repoId/observed`, the bindings route, `/detectors`, `/findings/:id`, `/findings/:id/workflow`, `…/workflow/pull-request` — subjects from the seed data), evaluate this in the page and record the result:

```js
(() => {
  const els = [...document.querySelectorAll("main *")].filter(
    (e) => e.offsetParent !== null && e.textContent.trim() !== ""
  );
  const sizes = els
    .map((e) => parseFloat(getComputedStyle(e).fontSize))
    .filter((n) => Number.isFinite(n));
  const containers = [...document.querySelectorAll("main *")].filter((e) => {
    const s = getComputedStyle(e);
    if (s.display !== "grid" && s.display !== "flex") return false;
    if (s.display === "flex" && s.flexDirection.startsWith("column")) return false;
    const kids = [...e.children].filter((k) => k.offsetParent !== null);
    if (kids.length < 2) return false;
    const tops = kids.map((k) => Math.round(k.getBoundingClientRect().top));
    return new Set(tops).size < kids.length; // at least two children share a row
  });
  const frame = parseFloat(getComputedStyle(document.querySelector("main")).paddingLeft);
  return {
    typeMax: Math.max(...sizes),
    typeMin: Math.min(...sizes),
    typeRange: (Math.max(...sizes) / Math.min(...sizes)).toFixed(2),
    sideBySideRegions: containers.length,
    framePx: frame,
  };
})()
```

- [ ] **Step 4: Write the report.** One row per screen: route, mock still filename, `typeRange` (bar: ≥ 3.4), `sideBySideRegions` (bar: ≥ 1 per level), `framePx`, and a verdict column per visible delta against the still — `adopt` / `adapt` / `refuse` with one sentence of reason. Note explicitly that mock fixtures (`acme/payments-api`, `#4127`) are layout weights, not data.
- [ ] **Step 5: `clear_viewport`, stop the worker dev server.**
- [ ] **Step 6: Commit:** `docs: M14-W<n> baseline mock-gap measurements for all nine routes`

---

## Phase 1 — chassis conformance

### Task 4: `DetailGrid`, one two-column shape instead of five literals

**Files:**
- Create: `web/src/layouts/detail-grid.tsx`
- Modify: `web/src/features/findings/finding-page.tsx:323`, `web/src/features/pullrequests/pull-request-page.tsx:242`, `web/src/features/workflows/workflow-page.tsx:267`, `web/src/features/vendors/vendor-page.tsx:90`, `web/src/features/bindings/binding-surface-page.tsx:367`
- Test: `web/src/layouts/detail-grid.test.tsx`

**Interfaces:**
- Produces: `DetailGrid({ rail, railSide?, header?, children })` — `rail: ReactNode`, `railSide?: "start" | "end"` (default `"start"`), `header?: ReactNode` (spans both columns), `children: ReactNode` (the content column). The two grid literals it owns are exactly the two that exist today: `lg:grid-cols-[minmax(0,22.5rem)_minmax(0,1fr)]` for `"start"`, `lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]` for `"end"`. No width prop — YAGNI until a third width exists.

- [ ] **Step 1: Write the failing test** (structural: DOM order, not class names)

```tsx
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { DetailGrid } from "@/layouts/detail-grid"

describe("DetailGrid", () => {
  it("renders header, then rail before content when railSide is start", () => {
    render(
      <DetailGrid header={<h1>head</h1>} rail={<nav>rail</nav>}>
        <p>content</p>
      </DetailGrid>
    )
    const all = screen.getByText("head").closest("div")!.parentElement!.textContent!
    expect(all.indexOf("head")).toBeLessThan(all.indexOf("rail"))
    expect(all.indexOf("rail")).toBeLessThan(all.indexOf("content"))
  })

  it("renders content before rail when railSide is end", () => {
    const { container } = render(
      <DetailGrid rail={<nav>rail</nav>} railSide="end">
        <p>content</p>
      </DetailGrid>
    )
    const text = container.textContent!
    expect(text.indexOf("content")).toBeLessThan(text.indexOf("rail"))
  })
})
```

- [ ] **Step 2: Run to verify RED:** `cd web && npx vitest run src/layouts/detail-grid.test.tsx` → FAIL, module not found.
- [ ] **Step 3: Implement**

```tsx
/**
 * The console's one two-column detail shape.
 *
 * Five screens spelled this grid by hand and two of them mirrored it; a sixth spelling
 * would eventually disagree with the other five. The two literals here are the two that
 * shipped — a rail width is a decision, and a third width is argued in DESIGN.md first.
 */

import type { ReactNode } from "react"

const SHAPE = {
  start: "lg:grid-cols-[minmax(0,22.5rem)_minmax(0,1fr)]",
  end: "lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]",
} as const

export function DetailGrid({
  rail,
  railSide = "start",
  header,
  children,
}: {
  rail: ReactNode
  railSide?: keyof typeof SHAPE
  /** Spans both columns — a `PageHeader`, usually. */
  header?: ReactNode
  children: ReactNode
}) {
  return (
    <section className={`grid items-start gap-8 ${SHAPE[railSide]}`}>
      {header !== undefined && <div className="lg:col-span-2">{header}</div>}
      {railSide === "start" ? (
        <>
          <div className="flex min-w-0 flex-col gap-8">{rail}</div>
          <div className="flex min-w-0 flex-col gap-8">{children}</div>
        </>
      ) : (
        <>
          <div className="flex min-w-0 flex-col gap-8">{children}</div>
          <div className="flex min-w-0 flex-col gap-8">{rail}</div>
        </>
      )}
    </section>
  )
}
```

- [ ] **Step 4: Run to verify PASS**, then adopt it in the five pages: replace each hand-spelled grid `section` with `DetailGrid`, keeping each page's exact child order and rail side (`finding`, `pull-request`, `workflow` use `railSide="start"`; `vendor`, `binding-surface` use `railSide="end"`). Do not change any prose while in these files.
- [ ] **Step 5: Gate:** `npm run build && npm run lint && npm test` — the five pages' existing tests stay green.
- [ ] **Step 6: Commit:** `feat: M14-W<n> DetailGrid replaces five hand-spelled two-column grids`

### Task 5: Fleet back on the chassis

**Files:**
- Create: `web/src/features/fleet/proposed-patch.ts`
- Modify: `web/src/features/fleet/fleet-page.tsx`
- Test: `web/src/features/fleet/proposed-patch.test.ts`

**Interfaces:**
- Consumes: `PageHeader` (`layouts/page-header.tsx` — props `title`, `question`, `trail`, `actions`), `ControlBar` (`layouts/control-bar.tsx` — `children`, `action`), `chipSurface` (`lib/selectable-surface.ts`), `useRuns` (`api/queries.ts`), `RunRow` (`api/types.ts`).
- Produces: `proposedPatchTarget(runs: RunRow[]): string | null` — the route of the newest run with `outcome === "opened"`, or null. Task 3's report and Task 15's walk read the fleet screen this task produces.

The screen's docstring already describes this composition (`fleet-page.tsx:31-66`); the code stopped matching it. This task makes the docstring true again. The hardcoded CTA link to `/findings/2f725b…` is fixture data rendered as fact and goes away.

- [ ] **Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest"

import { proposedPatchTarget } from "@/features/fleet/proposed-patch"
import type { RunRow } from "@/api/types"

const row = (over: Partial<RunRow>): RunRow => ({
  thread_id: "f1:abc:1",
  finding_id: "f1",
  current_node: null,
  outcome: null,
  abandon_reason: null,
  last_checkpoint_at: null,
  ...over,
})

describe("proposedPatchTarget", () => {
  it("is null when no run has opened a pull request", () => {
    expect(proposedPatchTarget([row({ outcome: "abandoned" }), row({})])).toBeNull()
  })

  it("names the first opened run's pull-request route", () => {
    const runs = [row({ outcome: "abandoned" }), row({ finding_id: "f9", outcome: "opened" })]
    expect(proposedPatchTarget(runs)).toBe("/findings/f9/workflow/pull-request")
  })

  it("is null on an empty list", () => {
    expect(proposedPatchTarget([])).toBeNull()
  })
})
```

- [ ] **Step 2: RED:** `npx vitest run src/features/fleet/proposed-patch.test.ts` → FAIL, module not found.
- [ ] **Step 3: Implement**

```ts
/**
 * Which pull request the fleet's one primary action reviews.
 *
 * `/api/runs` orders newest first, so the first `opened` row is the newest proposed
 * patch. No run opened means no action — a CTA pointing at an invented finding id is
 * fixture data rendered as fact, which is how the previous hardcoded link shipped.
 */

import type { RunRow } from "@/api/types"

export function proposedPatchTarget(runs: RunRow[]): string | null {
  const opened = runs.find((run) => run.outcome === "opened")
  if (opened === undefined) return null
  return `/findings/${encodeURIComponent(opened.finding_id)}/workflow/pull-request`
}
```

- [ ] **Step 4: PASS**, then recompose `fleet-page.tsx`:
  - Replace the hand-rolled title block (lines 112-131) with `PageHeader`: `title="Repositories"`, `question={question}`, `trail={<Breadcrumbs trail={[{ label: "Repositories" }]} />}`, `actions` = the CTA below.
  - CTA: `useRuns({ limit: 20, offset: 0 })` in the page; `const target = proposedPatchTarget(runsQuery.data?.items ?? [])`; render `<Button asChild><Link to={target}>Review proposed patch</Link></Button>` only when `target !== null` — the vendored `Button`'s default variant already resolves to `--color-primary`/`--color-primary-foreground`; every raw class on the old element (`bg-emerald-500 …`) is deleted, not ported.
  - Replace the three hand-rolled filter tab buttons with `chipSurface`-styled `Button`s (`size="sm" variant="outline"`, `aria-pressed`, `className={chipSurface(filter === value)}`) inside a `ControlBar` whose right slot is empty; keep the scope sentence as the bar's trailing text. One map over `[["ALL","All repositories"],["NEEDS_REVIEW","With active remediations"],["CLEAN","Clean repositories"]]` — no duplicated class strings.
  - Replace the hand-built "Health score policy" tile (lines 187-196) with `FactTile`: `label="Health score policy"`, `value` = the existing paragraph (the sentence is one of the honesty statements — every word survives verbatim).
  - Update the docstring's four-change list only where a claim changed; do not touch the three footnote paragraphs (protected sentences).
- [ ] **Step 5: Gate** (`npm run build && npm run lint && npm test`), then eyeball the running screen on a worker port: display-step title present, CTA absent when the seed has no opened run.
- [ ] **Step 6: Commit:** `feat: M14-W<n> fleet returns to the chassis; the CTA stops naming an invented finding`

### Task 6: `CodebasesPanel` tells the truth

**Files:**
- Create: `web/src/features/fleet/codebase-cards.ts`
- Rewrite: `web/src/features/fleet/codebases-panel.tsx`
- Test: `web/src/features/fleet/codebase-cards.test.ts`

**Interfaces:**
- Consumes: `useRepositories` (`repo_ids: string[]`), `fetchOverview({ repoId })` via a new `useRepoOverviews`, `OverviewResponse` (`repo_id`, `vendors`, `total_findings` — the payload echoes its own scope), `Badge` (vendored), `FactTile`-style tokens.
- Produces: `cardFacts(repoId, overview: OverviewResponse | undefined): CodebaseCardFacts` and `matchesFilter(facts, filter: CodebaseFilter): boolean`, where `CodebaseCardFacts = { repoId: string; openFindings: number | null; vendors: string[] }` (`openFindings` null while the scoped answer has not arrived — null is "not yet answered", never zero).

Current defects this task removes, from the 2026-08-17 audit: fleet-wide `total_findings` shown on every card; runs attributed to repositories the payload cannot attribute (`RunRow` has no `repo_id`); hue-carried judgement badges; `["acme/payments-api"]` and `"Stripe"` fallbacks; `"Index status: verified"` asserted with nothing behind it; nine raw-utility spellings.

- [ ] **Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest"

import { cardFacts, matchesFilter } from "@/features/fleet/codebase-cards"
import type { OverviewResponse } from "@/api/types"

const overview = (over: Partial<OverviewResponse>): OverviewResponse => ({
  repo_id: "org/repo",
  vendors: [],
  total_findings: 0,
  total_findings_bound: 0,
  total_findings_bound_reached: true,
  severity_counts: {},
  indexed_at: null,
  feed_fetched_at: null,
  binding_source: null,
  context_savings_bound_reached: true,
  ...over,
} as OverviewResponse)

describe("cardFacts", () => {
  it("holds openFindings null until the scoped answer arrives", () => {
    expect(cardFacts("org/repo", undefined).openFindings).toBeNull()
  })

  it("refuses an answer computed for a different scope", () => {
    const other = overview({ repo_id: "org/other", total_findings: 7 })
    expect(cardFacts("org/repo", other).openFindings).toBeNull()
  })

  it("carries the scoped count and vendor ids", () => {
    const scoped = overview({
      total_findings: 3,
      vendors: [{ vendor_id: "stripe" } as OverviewResponse["vendors"][number]],
    })
    const facts = cardFacts("org/repo", scoped)
    expect(facts.openFindings).toBe(3)
    expect(facts.vendors).toEqual(["stripe"])
  })
})

describe("matchesFilter", () => {
  const facts = (openFindings: number | null) => ({ repoId: "r", openFindings, vendors: [] })

  it("NEEDS_REVIEW takes only repos with a positive scoped count", () => {
    expect(matchesFilter(facts(2), "NEEDS_REVIEW")).toBe(true)
    expect(matchesFilter(facts(0), "NEEDS_REVIEW")).toBe(false)
    expect(matchesFilter(facts(null), "NEEDS_REVIEW")).toBe(false)
  })

  it("CLEAN takes only a confirmed zero — an unanswered scope is neither clean nor dirty", () => {
    expect(matchesFilter(facts(0), "CLEAN")).toBe(true)
    expect(matchesFilter(facts(null), "CLEAN")).toBe(false)
  })

  it("ALL takes everything", () => {
    expect(matchesFilter(facts(null), "ALL")).toBe(true)
  })
})
```

If `OverviewResponse`'s field list in `api/types.ts:115-128` differs from the stub above, follow the type — the stub is a sketch of shape, the type is the contract.

- [ ] **Step 2: RED**, module not found.
- [ ] **Step 3: Implement `codebase-cards.ts`**

```ts
/**
 * What one repository card may claim, computed from an answer scoped to that repository.
 *
 * `/api/overview` echoes the scope it was computed for; a fleet-wide figure rendered
 * under a repository's name is a false claim about that repository, which is exactly
 * what this panel used to do. `openFindings` stays null until the scoped answer for
 * this repository has arrived — null is "not yet answered" and renders as the absence
 * marker, never as zero and never as "Clean".
 */

import type { OverviewResponse } from "@/api/types"

export type CodebaseFilter = "ALL" | "NEEDS_REVIEW" | "CLEAN"

export interface CodebaseCardFacts {
  repoId: string
  openFindings: number | null
  vendors: string[]
}

export function cardFacts(
  repoId: string,
  overview: OverviewResponse | undefined
): CodebaseCardFacts {
  if (overview === undefined || overview.repo_id !== repoId) {
    return { repoId, openFindings: null, vendors: [] }
  }
  return {
    repoId,
    openFindings: overview.total_findings,
    vendors: overview.vendors.map((v) => v.vendor_id),
  }
}

export function matchesFilter(facts: CodebaseCardFacts, filter: CodebaseFilter): boolean {
  if (filter === "NEEDS_REVIEW") return facts.openFindings !== null && facts.openFindings > 0
  if (filter === "CLEAN") return facts.openFindings === 0
  return true
}
```

- [ ] **Step 4: PASS**, then rewrite `codebases-panel.tsx`:
  - Add `useRepoOverviews(repoIds: string[])` in the panel file using `useQueries` from `@tanstack/react-query`, mapping each id to `{ queryKey: ["overview", id], queryFn: ({ signal }) => fetchOverview({ repoId: id }, signal) }` (import `fetchOverview` from `@/api/client` — match `queries.ts:40-45`'s key shape so the caches cooperate).
  - Cards from `repo_ids` only — the `["acme/payments-api"]` fallback is deleted; an empty list renders `EmptyState` with the existing absence sentence pattern.
  - Badge: neutral vendored `Badge` (default variant, no colour classes): `{n} open findings` when `openFindings !== null && n > 0`; `No open findings` on a confirmed zero; `<Absent>` (from `components/status.tsx`) while null. Words only, no icon, no emerald, no amber.
  - Vendors row from `facts.vendors`; empty renders nothing (the count badge already says what the scope holds). The `"Stripe"` fallback is deleted.
  - The "Remediation active" row and the amber clock are deleted — `RunRow` carries no `repo_id`, so the panel cannot honestly attribute a run to a card; the runs table below the fold is where runs live. The `"Index status: verified"` line is deleted — nothing in any payload asserts it.
  - Every raw utility replaced with tokens (`rounded-md` → `rounded-control`, `text-xl` → `text-page` on the panel heading, `text-base` → `text-emphasis`, `py-0.5` → `py-field`). Move the panel's `CodebaseFilter` type import to `codebase-cards.ts` and re-export for `fleet-page.tsx`.
  - Write a real docstring: the scope-echo argument, the refused run attribution, the null-versus-zero distinction.
- [ ] **Step 5: Shrink the baseline:** delete this file's rows from `tests/console_raw_utilities_baseline.txt`; `uv run pytest tests/test_console_raw_utilities.py -q` → PASS proves they are gone.
- [ ] **Step 6: Gate** (`npm run build && npm run lint && npm test && uv run pytest tests/test_console_raw_utilities.py -q`), eyeball the running screen: cards show scoped counts, absence marker while loading, no green, no amber.
- [ ] **Step 7: Commit:** `feat: M14-W<n> codebase cards claim only what their own scope answered`

### Task 7: Raw-utility sweep to zero, docstrings made true

**Files:**
- Modify: every file remaining in `tests/console_raw_utilities_baseline.txt` (the audit names `change-units-table.tsx` with 5 as the largest remaining offender, plus ~12 others)
- Modify: `tests/console_raw_utilities_baseline.txt` → empty
- Modify: `web/src/features/workflows/superseded-generations.tsx:24`, `web/src/features/workflows/workflow-page.tsx:102`, `web/src/components/data-table.tsx:148` — the three `p-card`/bare-`rounded` spellings outside `features/`' baseline

**Interfaces:**
- Consumes: the Task 2 guard as the work list.
- Produces: an empty baseline; the guard now holds the line at zero.

- [ ] **Step 1:** For each baseline row, open the file and replace the raw utility with its token: text sizes map to the seven roles in `DESIGN.md:498-506` by *job* (a card's own title → `text-emphasis`, a section heading → `text-section`, furniture → `text-meta`); radius → `rounded-control` (6px, controls) or `rounded-surface` (8px, surfaces); spacing → `p-field`/`p-row`/`p-section` by the level it separates; any remaining palette colour is a judgement claim — delete it and let the word carry the fact. When a mapping is genuinely ambiguous, decide by job, record the ruling in the ledger below, and continue.
- [ ] **Step 2:** Empty the baseline file. Run: `uv run pytest tests/test_console_raw_utilities.py -q` → PASS with zero entries.
- [ ] **Step 3:** The three `p-card`/bare-`rounded` spellings outside `features/`: replace with `p-section` and `rounded-surface` (same pixel values; the spelling is the defect).
- [ ] **Step 4:** Docstring pass over every file touched in Phase 1: any sentence asserting a composition the code does not render is corrected to what ships. Protected sentences untouched — re-read every diff for a deleted qualification.
- [ ] **Step 5: Gate:** full — `cd web && npm run build && npm run lint && npm test`, `uv run pytest tests/ -q`.
- [ ] **Step 6: Commit:** `refactor: M14-W<n> raw utilities to zero across features; docstrings match what ships`

---

## Phase 2 — composition gaps

### Task 8: Breadcrumbs on the two bare routes

**Files:**
- Modify: `web/src/features/vendors/vendor-page.tsx` (header region, `:83-146`), `web/src/features/repositories/codebase-page.tsx` (header region, `:249-289`)
- Test: extend `web/src/features/vendors/` and `web/src/features/repositories/` page tests where trail structure is asserted; otherwise structural assertions in a new small test per page.

**Interfaces:**
- Consumes: `Breadcrumbs` (`layouts/breadcrumbs.tsx` — `trail: { label: string; href?: string }[]`), `PageHeader`'s `trail` prop.

- [ ] **Step 1: Failing test** (one per page, structural): render the page with a mocked query returning a subject; assert a navigation landmark contains "Repositories" as a link to `/` and the subject as the terminal crumb. Follow the existing pattern in `web/src/layouts/app-frame.test.tsx` for mocking.
- [ ] **Step 2: RED.**
- [ ] **Step 3:** Pass `trail={<Breadcrumbs trail={[{ label: "Repositories", href: "/" }, { label: subjectId }]} />}` into each page's `PageHeader`.
- [ ] **Step 4: PASS, gate, commit:** `feat: M14-W<n> vendor and codebase say what contains them`

### Task 9: The disposition chart stops spending hue on a categorical axis

**Files:**
- Modify: `web/src/features/fleet/corpus-chart.tsx` (option builder near `:151`)
- Test: `web/src/features/fleet/corpus-chart-option.test.ts` (new; mirror the pattern of `web/src/features/detectors/rung-composition-option.test.ts`)

**Interfaces:**
- Consumes: the chart's existing option-builder; the `EChart` wrapper's token-resolved `colors` argument.
- Produces: an exported `dispositionOption(data, colors)` (extract it if the file builds options inline) whose every series/bar resolves to one colour.

The recorded invariant (`plans/2026-08-07-m12-dashboards-that-earn-their-screen.md:79-81`): a chart's colour may not carry a fact its length or position already carries. Disposition categories are named by their axis labels; length carries the count.

- [ ] **Step 1: Failing test:** build the option from a three-category fixture; collect every `itemStyle.color`/series colour the option declares; assert the set has exactly one member.
- [ ] **Step 2: RED** against the current multi-hue builder.
- [ ] **Step 3:** One colour token for all disposition bars (the wrapper's first series slot); category identity stays on the axis label.
- [ ] **Step 4: PASS, gate, eyeball the running chart, commit:** `fix: M14-W<n> disposition bars carry their fact by length, not hue`

---

## Phase 3 — the trajectory flagship

### Task 10: The activity timeline, derived and rendered

**Files:**
- Create: `web/src/features/workflows/activity.ts`
- Create: `web/src/features/workflows/activity-timeline.tsx`
- Test: `web/src/features/workflows/activity.test.ts`

**Interfaces:**
- Consumes: `WorkflowState`, `WorkflowNode`, `NodeStanding` (`api/types.ts:280-357`).
- Produces:
  - `activityEntries(state: WorkflowState): ActivityEntry[]` with `ActivityEntry = { at: string | null; name: string; detail: string | null }` — `name` is `"<node>.<verb>"` (`ran` → `ran`, `due`/`due_again` → `due`, outcome entry `run.<outcome>`); sorted by `at` ascending, entries with `at: null` last.
  - `omittedCount(state: WorkflowState): number` — nodes that produced no timestamp and therefore no entry.
  - `<ActivityTimeline state={WorkflowState} />` — rendered rows of time (mono), name (mono), detail.

Honesty boundary, stated here because the mock invents what we must not: mock screen 07's timeline shows CI events and PR events with their own timestamps. Our payload carries node checkpoints only. The timeline renders what the checkpointer holds — an entry per node that wrote `first_seen_at`, and one unstamped closing entry for the outcome (the payload records no outcome timestamp; inventing one from the last node would claim a time the data does not hold). The panel's caption carries the mock's own honesty sentence, adapted: "Assembled at read time from the checkpointer. Nothing writes a timeline row."

- [ ] **Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest"

import { activityEntries, omittedCount } from "@/features/workflows/activity"
import type { WorkflowState, WorkflowNode } from "@/api/types"

const node = (over: Partial<WorkflowNode>): WorkflowNode => ({
  name: "locate",
  status: "done",
  standing: "ran",
  evidence: {},
  ...over,
})

const state = (nodes: WorkflowNode[], over: Partial<WorkflowState> = {}): WorkflowState => ({
  nodes,
  outcome: null,
  abandon_reason: null,
  report_reason: null,
  thread_id: "f1:abc:1",
  generation_count: 1,
  repo_id: null,
  generations: [],
  ...over,
})

describe("activityEntries", () => {
  it("orders stamped entries by time and puts the unstamped outcome last", () => {
    const s = state(
      [
        node({ name: "prepare", first_seen_at: "2026-08-17T14:02:31Z" }),
        node({ name: "locate", first_seen_at: "2026-08-17T14:02:14Z" }),
      ],
      { outcome: "opened" }
    )
    const names = activityEntries(s).map((e) => e.name)
    expect(names).toEqual(["locate.ran", "prepare.ran", "run.opened"])
    expect(activityEntries(s).at(-1)!.at).toBeNull()
  })

  it("emits no entry for a node that never wrote a timestamp, and counts it", () => {
    const s = state([
      node({ name: "locate", first_seen_at: "2026-08-17T14:02:14Z" }),
      node({ name: "patch", standing: "not_reached_yet" }),
    ])
    expect(activityEntries(s).map((e) => e.name)).toEqual(["locate.ran"])
    expect(omittedCount(s)).toBe(1)
  })

  it("carries the abandon reason as the closing entry's detail", () => {
    const s = state([node({ first_seen_at: "2026-08-17T14:02:14Z" })], {
      outcome: "abandoned",
      abandon_reason: "no tier applied",
    })
    const closing = activityEntries(s).at(-1)!
    expect(closing.name).toBe("run.abandoned")
    expect(closing.detail).toBe("no tier applied")
  })

  it("emits no closing entry while the run has no outcome", () => {
    const s = state([node({ first_seen_at: "2026-08-17T14:02:14Z" })])
    expect(activityEntries(s).some((e) => e.name.startsWith("run."))).toBe(false)
  })
})
```

- [ ] **Step 2: RED**, module not found.
- [ ] **Step 3: Implement `activity.ts`.** Per node with a `first_seen_at`: `{ at, name: \`${node.name}.${verb(node.standing)}\`, detail: primaryDetail(node) }` where `verb` maps `ran → "ran"`, `due`/`due_again` → `"due"`, and the not-reached standings never appear (they have no timestamp by construction — if one does, emit it; the data wins). `primaryDetail(node)`: the first evidence value whose type is `string` under the node's own keys, else null — reuse `FIELDS` from `evidence.tsx` if its shape offers labels cheaply; do not build a second evidence vocabulary. Closing entry only when `outcome !== null`: `{ at: null, name: \`run.${outcome}\`, detail: abandon_reason ?? report_reason ?? null }`. Sort stamped ascending by `Date.parse`, nulls last, stable.
- [ ] **Step 4: PASS**, then `activity-timeline.tsx`: a `MetricPanel` titled "Activity" whose body is an `<ol>` — each row `grid-cols-[auto_1fr]`: `<time>` mono `text-meta` (or the absence marker for null), then the mono entry name with the detail sentence under it in `text-meta text-ink-muted`. Caption under the title: "Assembled at read time from the checkpointer. Nothing writes a timeline row." When `omittedCount > 0`, close the list with one sentence: "N nodes have written no checkpoint timestamp and have no row here — absence, not zero."
- [ ] **Step 5: Gate, commit:** `feat: M14-W<n> the activity timeline, derived from checkpoints and nothing else`

### Task 11: Node sequence dynamics — disclosure, recession, evidence age

**Files:**
- Modify: `web/src/features/workflows/node-sequence.tsx`
- Create: `web/src/features/workflows/sequence-dynamics.ts`
- Test: `web/src/features/workflows/sequence-dynamics.test.ts`, extend `web/src/features/workflows/node-sequence.test.tsx`

**Interfaces:**
- Consumes: `NodeStanding`, `WorkflowNode`, `useNow`/`secondsSince`/`formatAge` (`lib/elapsed.ts`), `closingEntryIndex` (`narrative-order.ts`).
- Produces, in `sequence-dynamics.ts`:
  - `inkFor(standing: NodeStanding): "default" | "receded"` — `not_reached_yet` and `never_reached` recede; everything else default.
  - `latestEvidenceAt(nodes: WorkflowNode[]): string | null` — max of every `last_seen_at ?? first_seen_at`.
  - `defaultDisclosed(index: number, lastReachedIndex: number): boolean` — only the last reached node opens by default.

No pulse anywhere in this task — spec ruling 2. The ticking figure is labelled as evidence age, never as activity.

- [ ] **Step 1: Failing tests** for the three helpers:

```ts
import { describe, expect, it } from "vitest"

import { defaultDisclosed, inkFor, latestEvidenceAt } from "@/features/workflows/sequence-dynamics"

describe("inkFor", () => {
  it("recedes only the unreached standings", () => {
    expect(inkFor("not_reached_yet")).toBe("receded")
    expect(inkFor("never_reached")).toBe("receded")
    expect(inkFor("ran")).toBe("default")
    expect(inkFor("due")).toBe("default")
    expect(inkFor("due_again")).toBe("default")
  })
})

describe("latestEvidenceAt", () => {
  it("takes the newest of last_seen_at falling back to first_seen_at", () => {
    const nodes = [
      { last_seen_at: "2026-08-17T14:03:00Z", first_seen_at: "2026-08-17T14:02:00Z" },
      { last_seen_at: null, first_seen_at: "2026-08-17T14:05:00Z" },
    ]
    expect(latestEvidenceAt(nodes as never)).toBe("2026-08-17T14:05:00Z")
  })

  it("is null when nothing was stamped", () => {
    expect(latestEvidenceAt([{ evidence: {} }] as never)).toBeNull()
  })
})

describe("defaultDisclosed", () => {
  it("opens only the last reached node", () => {
    expect(defaultDisclosed(3, 3)).toBe(true)
    expect(defaultDisclosed(2, 3)).toBe(false)
  })
})
```

- [ ] **Step 2: RED. Step 3: Implement the helpers** (each is a few lines; the types come from the test).
- [ ] **Step 4:** Wire into `node-sequence.tsx`:
  - `StepBody` wraps `NodeEvidence` in a disclosure: a `<button type="button" aria-expanded={open} aria-controls={id}>` labelled `evidence` (with the count of present keys), toggling local state initialised from `defaultDisclosed`. Evidence blocks are data, not protected sentences — disclosure is legal here; the standing label, timestamp, and purpose sentence stay outside the disclosure, always visible.
  - Node name and purpose sentence take `text-ink-muted` when `inkFor(standing) === "receded"`; markers stay exactly as they are (monochrome, three appearances).
  - When the run's `outcome === null` and `latestEvidenceAt` is non-null, render beside the due node: `formatAge(secondsSince(Date.parse(latest), now))` with `useNow(1000)`, labelled "since last evidence — staleness, not liveness". Reduced motion keeps the ticking figure: it is information, not movement (the precedent is `LoadingState`, M7-W218).
- [ ] **Step 5:** Extend `node-sequence.test.tsx` (RTL, structural): evidence hidden until the button is clicked on a non-default node; the due node's body contains "since last evidence" when the fixture run is unfinished and stamped; a finished run renders no ticking label.
- [ ] **Step 6: Gate, eyeball, commit:** `feat: M14-W<n> node sequence gains disclosure, recession, and an honest evidence age`

### Task 12: The workflow route recomposed to mock screen 07

**Files:**
- Modify: `web/src/features/workflows/workflow-page.tsx`
- Test: extend existing workflow page coverage (`node-sequence.test.tsx` untouched; page-level structural test if one exists, else add `workflow-page.test.tsx` asserting region order)

**Interfaces:**
- Consumes: `DetailGrid` (Task 4), `ActivityTimeline` (Task 10), the dynamic `NodeSequence` (Task 11), `MetricPanel`, `FactList`.

Mock screen 07's shape: left card "Node by node" (compact sequence, outcome at its foot), right card "Activity". The current page already renders `RunOutcome` as the sequence's closing bracket entry (`narrative-order.ts`) — that stays; it is the feature's core idea and the mock draws the same thing.

- [ ] **Step 1: Failing structural test:** render the page with a mocked `useWorkflow` fixture; assert the accessible region/heading order is: page header, then "Node by node", then "Activity"; assert the run facts (`FactList`) render inside the rail column before the sequence.
- [ ] **Step 2: RED.**
- [ ] **Step 3: Recompose:** `DetailGrid` with `railSide="start"`, `header` = the existing `PageHeader`; rail = `FactList` (run facts, unchanged) + a `MetricPanel` titled "Node by node" wrapping `NodeSequence` (its intro sentence: "Eight nodes, in the order the graph wires them. A standing is the checkpoint's own answer — nothing here says a node is executing." — this sentence exists in the mock and matches the `NODE_STANDINGS` docstring's claim; carry it); content = `FetchedAt`/`StaleBanner` block, `ActivityTimeline`, `SupersededGenerations`. Nothing about `narrative-order` changes.
- [ ] **Step 4: PASS, full gate, eyeball at 1440×900** against `docs/console-mock/screens/07-workflow.png` — composition matches; fixtures differ (theirs are invented).
- [ ] **Step 5: Commit:** `feat: M14-W<n> the workflow route takes the mock's two-pane trajectory shape`

---

## Phase 4 — destinations and the closing walk

### Task 13: `/settings` as a destination, not a tenth level

**Files:**
- Create: `web/src/features/settings/settings-page.tsx`
- Modify: `web/src/lib/routes.ts` (add `DESTINATION_ROUTES`), `web/src/App.tsx`, `web/src/layouts/app-frame.tsx` (the existing "Settings & adapters" footer entry becomes a link), `web/src/layouts/command-palette.tsx` (destinations group)
- Test: `web/src/features/settings/settings-page.test.tsx`, extend `web/src/lib/routes.test.tsx`

**Interfaces:**
- Produces: `DESTINATION_ROUTES: { path: string; label: string; question: string; component: … }[]` — a separate array; `ROUTES` and `GRAPH_LEVELS` are untouched, so `tests/test_console_hierarchy.py` (which parses them) is untouched. `/settings` is its only member.
- The page states absence rather than inventing: the read surface (`src/sync/api/app.py:374-394`) has no adapter-registry or merge-policy route, so the page renders `PageHeader` (question: "What Sync is configured to watch, and what this console can and cannot see of it."), the areas/levels explanation the sidebar footer currently carries, and two `EmptyState` panels — "Adapters" ("The read surface has no adapter registry route. Intake provenance is not visible from this console until one exists.") and "Merge policy" (same shape). This is mock-to-build Task 5's own instruction: "state absence where the API has no field yet rather than inventing one."

- [ ] **Step 1: Failing tests:** `routes.test.tsx` — `GRAPH_LEVELS.length === 9` still, and `DESTINATION_ROUTES` contains `/settings` with no `level` property; `settings-page.test.tsx` — the page renders the two absence sentences and the display-step title.
- [ ] **Step 2: RED. Step 3: Implement** the array, the route in `App.tsx` (beside the `*` route, before it), the sidebar link, and a "Destinations" group in the palette (zero-param, so it is a live link).
- [ ] **Step 4: PASS, full gate** including `uv run pytest tests/test_console_hierarchy.py -q` (must stay green untouched — that is the proof `/settings` did not become a level).
- [ ] **Step 5: Commit:** `feat: M14-W<n> /settings exists as a destination and says what it cannot see`

### Task 14: The palette lists subject-taking routes as lookups

**Files:**
- Modify: `web/src/layouts/command-palette.tsx`
- Test: `web/src/layouts/command-palette.test.tsx` (new)

**Interfaces:**
- Consumes: `ROUTES`, `DESTINATION_ROUTES`, `destinationHref` (`routes.ts:360` — all-or-nothing by param).

Today the palette lists only the two zero-param routes (`command-palette.tsx:115-134`). The mock's footer states the rule this task implements: a destination needing a subject is listed as a place to look one up, never as a link with an empty parameter.

- [ ] **Step 1: Failing test:** render the palette open; assert every entry of `ROUTES` appears grouped by area; assert a subject-taking route (e.g. the vendor route) renders as non-link text carrying its route pattern and its `reachedFrom` sentence, and a zero-param route renders as a link.
- [ ] **Step 2: RED. Step 3: Implement:** one map over `ROUTES` — `params.length === 0` renders the existing link item; otherwise a disabled item showing `label`, the path pattern in mono, and the registry's `reachedFrom` text. `ROUTES` stays the single source, so a new route appears here for free.
- [ ] **Step 4: PASS, gate, commit:** `feat: M14-W<n> the palette maps every destination honestly`

### Task 15: Closing measured walk

**Files:**
- Modify: `docs/superpowers/reports/2026-08-17-console-mock-gaps.md` (append the closing run)
- Modify: `docs/superpowers/BACKLOG.md` (M14 row to its true status)

**Interfaces:**
- Consumes: Task 3's baseline numbers and measurement snippet, all twelve mock stills.

- [ ] **Step 1:** Repeat Task 3's walk exactly (same viewport, same snippet, same routes, plus `/settings`). Append a closing table beside the baseline numbers: type range (bar ≥ 3.4 every route), side-by-side regions (bar ≥ 1 every level), frame px, raw-utility count (from the now-empty baseline), verdict per screen against its still.
- [ ] **Step 2:** Success criteria from the spec, checked one by one in the report: display step on every route; regions beside regions on every level; raw utilities zero; no colour-carried judgement outside the three channels; workflow route matches mock 07's composition; ledgers agree with the tree. Any criterion not met gets a named follow-up in `BACKLOG.md`, not a shrug.
- [ ] **Step 3:** `clear_viewport`, stop the worker server. Full local gate one last time: `uv run pytest tests/ -q`, `cd web && npm run build && npm run lint && npm test`. State which ran.
- [ ] **Step 4: Commit:** `docs: M14-W<n> closing mock-gap walk; M14 status recorded true`

---

## SDD ledger

Rulings made during execution land here: what was decided, what it was decided against, why. Three rulings arrived from the owner before execution and are recorded in the spec: whole-console scope; the liveness-pulse refusal stands; Remotion deferred. One ruling is made by this plan itself:

- **W226's `NODE_STRATEGY_EXPLANATIONS` gets rehomed by Task 11.** `c8b061d` (another session,
  2026-08-17) added a static per-node description under a "Reasoning & Strategy" disclosure inside
  `NodeEvidence`. The text is generic — the same words for every run — but its title and placement
  inside the *evidence* block let it read as reasoning the run recorded, which is a claim the data
  does not hold. Task 11's executor moves it beside the `PURPOSE` sentence (which is the same kind
  of static text, honestly placed) and retitles it "How this node works", or folds it into
  `PURPOSE` outright. The words may stay; the frame may not.
- **The shared `detail-drawer` extraction (mock-to-build Task 3) is refused for now.** `binding-drawer.tsx` is the only consumer in the tree; extracting a shared component for one caller violates "factor at the second use, not the third" (`CLAUDE.md`). The extraction happens in the task that adds a second drawer, whichever plan that lands in. `BACKLOG.md` carries the pointer (Task 1 writes it).
