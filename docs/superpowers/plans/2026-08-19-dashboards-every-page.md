# Dashboards on every page: the full catalogue, existing and proposed

**Owner direction, 2026-08-19:** *"evenly distribute dashboards that are crucial and beneficial to
each one of the pages … do this for all pages that are missing visuals and have a reason and
numbers and data to create dashboards … let's go through all the existing ones as well."*

**Owner rulings taken as given** (asked and answered the same day):

1. **NextAdmin is a conventions reference, never a code source** — and this is measured rather
   than assumed. The owner supplied `github.com/NextAdminHQ/nextjs-admin-dashboard`; queried
   2026-08-19, it reports **`license: null` and carries no LICENSE file**, which under default
   copyright is all-rights-reserved. Public and readable is not licensed: there is no grant to
   copy, modify or redistribute, and the paid edition is a commercial product besides. So
   nothing of its code enters this repository, and what transfers is what
   `.claude/rules/interface-originality.md` already permits — the KPI tile strip, the chart-card
   composition, the grid rhythm. **This is the same standard the Supabase carve-out met and
   NextAdmin does not**: that one is Apache-2.0, vendored with attribution in `web/NOTICE`, on
   the owner's recorded ruling. No carve-out is requested here and none could be written.
2. **Every page opens with a KPI tile strip**, then its charts, then its table.
3. **Balanced grid**: strip → two-column chart grid at equal heights → full-width table. One
   skeleton, so every page reads as one product.

## The rule that outranks the layout, restated because a dashboard is where it breaks

`2026-08-18-dashboards.md` holds it and nothing here amends it: **a chart may render a count, a
duration, or a distribution over a closed vocabulary. It may not render a composite.** No health
figure, no score, no gauge averaging two facts. A KPI tile carries one measured number and what it
was counted over — a tile that averaged two would be the scalar this console refuses.

**And a tile may not restate the table beneath it at the same weight.** `corpus-chart.tsx` already
records two KPI figures being removed for exactly that. A tile earns its place by answering a
question the table does not: a total the page is filtered away from, a distribution the rows do not
sum, a date the rows do not carry.

---

## The catalogue, page by page

Each entry names the source, so nothing here is speculative. **STATUS** is what exists today.

### Overview — `/repositories/:repoId`

**Existing:** Getting started checklist · force map · API topology card · technical census ·
open findings card · index coverage card · change units table · observed telemetry.

| # | Dashboard | Source | Status |
|---|---|---|---|
| O1 | KPI strip: call sites · integrations · open findings · last indexed | `/topology` totals, `/overview`, `/coverage` | **propose** |
| O2 | Bindings by rung — horizontal stacked bar | needs `by_rung` on `/overview` (plan #2's open half) | **propose (API work)** |
| O3 | Findings by kind over time | `/findings/over-time` | built, on Trends — **question: also here?** |
| O4 | Codebase map (force) | `/graph` | built |
| O5 | API topology (fan-in, coupling, loops) | `/topology` | built |

### Metrics → Findings — `/repositories/:repoId/findings`

**Existing:** triage tabs with per-kind counts · findings table.

| # | Dashboard | Source | Status |
|---|---|---|---|
| F1 | KPI strip: open findings · kinds present · newest finding · detectors reporting | `severity_counts`, `/detectors` | **propose** |
| F2 | Severity mix — donut or horizontal bar over `severity_counts` | already in payload | **propose** |
| F3 | Findings per integration — ranked bars | `/overview` vendors | **propose** |

### Metrics → Detectors — `/repositories/:repoId/detectors`

**Existing:** rung composition chart · detector attribution table.

| # | Dashboard | Source | Status |
|---|---|---|---|
| D1 | KPI strip: detectors reporting · findings attributed · rungs present | `/detectors` | **propose** |
| D2 | Findings per detector — ranked bars | `/detectors` rows | **propose** |
| D3 | Rung composition per detector | `/detectors` | built |

### Metrics → Trends — `/repositories/:repoId/metrics`

**Existing:** findings over time · observed volume. *Thin — this should be the analytics page.*

| # | Dashboard | Source | Status |
|---|---|---|---|
| T1 | KPI strip: findings this period · change in period · runs · integrations changed | several | **propose** |
| T2 | Findings by kind over time | `/findings/over-time` | built |
| T3 | Integration change volume over time | `/integration-changes` `detected_at` | **propose** |
| T4 | Run outcomes over time | `/runs` `last_checkpoint_at` + outcome | **propose** |
| T5 | Observed-call volume | `/observed` | built |

### Call sites — `/repositories/:repoId/call-sites`

**Existing:** filter rail · typed table.

| # | Dashboard | Source | Status |
|---|---|---|---|
| C1 | KPI strip: call sites · files · operations · integrations | `/topology` totals | **propose** |
| C2 | Call sites per integration — ranked bars | `by_vendor` facet already fetched | **propose** |
| C3 | Loop-depth distribution | `/topology` `by_loop_depth` | **propose** |

### Integrations — `/repositories/:repoId/vendors`

**Existing:** vendor cards · tier filters · table.

| # | Dashboard | Source | Status |
|---|---|---|---|
| I1 | KPI strip: integrations in use · staged · available · changes recorded | `/integrations` catalogue | **propose** |
| I2 | Adapter coverage by tier | `/adapters` | built (Settings) — **question: mirror here?** |
| I3 | Open findings per integration | `/overview` vendors | **propose** |

### Integrations → Changes — `/repositories/:repoId/integration-changes`

**Existing:** two filter rails · changes table.

| # | Dashboard | Source | Status |
|---|---|---|---|
| G1 | KPI strip: changes recorded · integrations publishing · breaking share · newest change | `/integration-changes` facets | **propose** |
| G2 | Change volume over time, per integration | `detected_at` + `vendor_id` | **propose** |
| G3 | Severity mix per integration — stacked bars | `by_vendor` × `by_severity` | **propose (needs a cross-facet)** |

### Connections — `/repositories/:repoId/services` — *no visuals today*

**Existing:** services table only.

| # | Dashboard | Source | Status |
|---|---|---|---|
| N1 | KPI strip: services connected · with open findings · indexed · never indexed | `/coverage` + `/overview` | **propose** |
| N2 | Call sites per service — ranked bars | `/coverage` `by_vendor` | **propose** |
| N3 | Index freshness per service — dated rows, oldest first | `/coverage` `last_indexed` | **propose** |

### Logs → Runs — `/repositories/:repoId/runs`

**Existing:** filter rail · runs table · abandon reasons · tier outcomes.

| # | Dashboard | Source | Status |
|---|---|---|---|
| R1 | KPI strip: runs · opened · abandoned · in flight | `by_disposition` already in payload | **propose** |
| R2 | Abandon reasons — ranked bars | `/corpus/abandonment` | built |
| R3 | Attempt outcomes by tier | `/corpus` | built |
| R4 | Run throughput over time | `last_checkpoint_at` | **propose** |

### Logs → Signals — `/repositories/:repoId/observed`

**Existing:** subject catalogue · signal source panel · observed volume card.

| # | Dashboard | Source | Status |
|---|---|---|---|
| S1 | KPI strip: sources attached · calls observed · shapes recorded · error windows | `/observed` | **propose** |
| S2 | Observed-call volume per operation | `/observed` | built |
| S3 | Error windows over time | `observed_error_window` | **propose** |

### Solutions — `/repositories/:repoId/solutions` — *no visuals today*

**Existing:** table only.

| # | Dashboard | Source | Status |
|---|---|---|---|
| L1 | KPI strip: pull requests opened · findings behind them · newest · merge policy | `/runs?outcome=opened`, settings | **propose** |
| L2 | Pull requests over time | `last_checkpoint_at` | **propose** |
| L3 | Tier that produced each solution | `/corpus` by tier, filtered to opened | **propose** |

### Settings — `/settings`

**Existing:** adapter coverage chart · adapter table · setup checklist · catalogue · staging.

No KPI strip proposed: Settings is a configuration surface rather than an analytics one, and a
tile row there would be decoration. **Question below.**

---

## What stays refused, on every page

- No health score, readiness gauge, uptime ring, or composite of any kind.
- No latency percentiles — there is no timing data with a denominator we trust.
- No prediction of what *would* upgrade or break.
- No sparkline whose axis is not stated, and no chart of a period the data does not cover.
- **No tile restating its own table's footer count at the same weight.**
