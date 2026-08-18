# Dashboards: what to build, from data we actually hold

**Owner direction, 2026-08-18:** *"we need to implement more dashboards … start planning out
dashboards that can be built and use reference information for what they should look like."*

**Measured first: the console has one chart.** `features/detectors/rung-composition-chart.tsx` is the
only visualisation in the tree. Every other screen is tiles, tables and prose. So this is close to a
standing start, and the constraint is not taste — it is what the graph can answer.

## The rule every dashboard on this list obeys

**A chart may render a count, a duration, or a distribution over a closed vocabulary. It may not
render a composite.** No health figure, no score, no gauge averaging two facts, no traffic light.
`CLAUDE.md` refuses those on the record three times, and a chart is the most tempting place to
reintroduce one because a gauge looks like a measurement.

**And every dashboard states its own provenance.** A count of bindings is not a count of bindings —
it is a count *at a rung*, and the rung goes on the chart.

## The nine, ordered by how much they answer for how little they cost

### 1. Findings by kind, over time — Overview
Stacked bars per day: breaking, deprecation, warning. **The single most legible thing we can draw**,
because it is the product's output. Reference shape: the per-service bars on the Supabase project
overview, which pair a count with its warning and error split.

### 2. Bindings by rung — Overview and Codebase
A horizontal stacked bar: `static`, `resolved`, `observed`, with `unresolved` and `unattributed`
shown apart under a heading that says they are not on the path. **This is the upgrade path made
visual** (`M14-W372`) and it is the chart that explains what Sync knows and how it knows it.

### 3. Call sites per vendor — Codebase
Horizontal bars, sorted. Answers *where is my exposure* in one glance, and it is pure count data.

### 4. Vendor change volume, per vendor, over time — Vendor
How often this vendor breaks things. **This is the number a reader most wants and cannot get
anywhere else**, and it is exactly what a self-maintaining-API product should be able to show.

### 5. Attempt outcomes by tier — Runs
Grouped bars: tier 0/1/2 against outcome. Shows the routing cascade working. Currently four rows, so
**it will be sparse and must say so** rather than looking broken.

### 6. Abandon reasons — Runs
A ranked bar over the closed `abandon_reason` vocabulary. `B128`'s whole argument was that a reason
must be aggregatable; this is the aggregation, and it is where routing learns.

### 7. Observed-call volume per operation — Signals
Sparkline per operation. Only meaningful where telemetry is attached, so **the empty state must say
*never measured*, not zero** — the distinction this console exists for.

### 8. Index freshness — Overview
Not a chart: a single dated fact with its age. **Included because staleness is the failure a
dashboard hides best** — a beautiful graph of month-old data is worse than no graph.

### 9. Adapter coverage by tier — Settings/Adapters
`coded`, `configured`, `generated` per vendor. Shows the plugin story is real rather than claimed.

## What is deliberately not on this list

- **Anything resembling a health score, an uptime ring, or a readiness gauge.**
- **Latency percentiles.** We have no timing data with a denominator we trust.
- **A globe.** The reference has one; we have no geography, and drawing a map of nothing is the
  clearest possible example of a claim our data cannot support.
- **Predictions.** No estimate of how many bindings *would* upgrade, per `M14-W372`.

## Where the data comes from, so nothing here is speculative

| Dashboard | Source |
|---|---|
| 1, 2, 3 | `/api/overview` and the scoped findings route |
| 4 | `vendor_change` joined to `vendor` |
| 5, 6 | `migration_outcome` — **grain is one attempt, not one finding** |
| 7 | `observed_call`, with `telemetry_attached_at` deciding empty-versus-absent (`B157`) |
| 8 | `indexed_at`, already on `/api/overview` |
| 9 | the adapter registry |

**Two of these need API work before the chart can exist** — 4 and 6 have no route. Lane G owns both
the dashboards and the API, which is why this is one lane's plan rather than two.

## Component

`chart` is in the batch Lane B is vendoring (`M0-W326`). **Do not hand-roll SVG** while that lands.
