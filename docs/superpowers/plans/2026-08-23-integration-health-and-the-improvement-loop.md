# Integration health on the row, test signals, and the improvement loop

Three features the owner asked for on 2026-08-23, planned together because they are one pipeline:
**see** the health of an integration, **exercise** it on demand, and **improve** it from what the
exercise measured.

Researched against the tree before planning. The headline is that far less of this is new than it
looks: the measurements exist, the eval axes exist, and the credential pattern exists and has
already been ruled on.

## What is already built, and where

| The feature seems to need | It already exists at | Verified |
|---|---|---|
| Per-vendor call volume, rung mix, freshness | `observed_call` — `vendor_id`, `operation_id`, `binding_rung`, `spans`, `first_seen`, `last_seen` | `graph/schema.sql:381` |
| Per-vendor health | `observed_error_window` — `status_class`, `error_count`, `issue_count`, `source`, window bounds | `graph/schema.sql:449` |
| A closed vocabulary for "rings" | `BindingRung = "static" \| "resolved" \| "observed" \| "unresolved"` | `core/models.py:54` |
| Speed, cost and accuracy scoring | `routing_accuracy`, `tokens_per_merged_patch`, `wall_ms_per_merged_patch` | `benchmark/axes.py:120-122` |
| A credential we never hold | `SYNC_MODEL_API_KEY` read to answer *is one present*, never stored, absent from `repr()`/`describe()` | `runner/provider.py`, `test_model_provider.py` |
| A solution-workflow entry point | `remediation_ticket` — `finding_id`, `source`, `status`, `thread_id`, `outcome`, `detail` | `graph/schema.sql:772` |

**The row strip needs no new capture at all.** It is an aggregation read over two tables that are
already populated. That is the single most important finding here.

## Feature 1 — the health strip on every vendor and service row

Vendor rows are `Vendor | Adapter Tier | Services called | Call sites` today
(`repository-vendors-page.tsx:284-287`). Service rows are `Operations | Vendor / service | Last
indexed` (`repository-services-page.tsx:398-400`). Both gain one column.

### Three zones, each answering one question

```
   WATCH        RUNGS                     HEALTH
     ◆     ███████▊▎░░░  1,204              ●
```

- **Watch** — one glyph. Can we see this vendor's specification at all? Filled where a spec was
  fetched at a known hash; hollow where the manifest is genuine and names none (Cloudflare, and
  that is not a fault); struck through where the manifest is unreachable (OpenAI's 404). This puts
  the measured 6-of-16 coverage into the UI, which is board item **A9**.
- **Rungs** — a four-segment micro bar over `observed_call.binding_rung`, plus the call count. The
  vocabulary is closed at four, so this is a fixed design rather than an open-ended one. This is
  the owner's "different rings".
- **Health** — one dot from `observed_error_window`.

### The rule that governs the whole component

**Absent must never render as healthy.** A green dot that means "no telemetry is attached" is
precisely the lie this codebase is organised against — `schema.sql` already argues that absent and
believed present is worse than absent, and `StatusSegment` already carries `{ kind: "none", why }`
for exactly this. The no-data state gets its own **shape**, not a calm grey fill.

### Accessibility is machine-enforced, per owner ruling 5

Colour is never the only channel. Every state differs in shape or fill as well as hue, and the
strip carries an accessible name containing the real numbers.

### Guards, because prose decays

- **G1** every health state differs from every other in a non-colour channel.
- **G2** the no-telemetry state never emits the healthy token.
- **G3** the rung segments sum to the stated call count — no rounding that invents a call.
- **G4** a vendor whose specification is unreachable cannot render the watched glyph.
- **G5** the strip's accessible name contains the counts it draws.

### Shape of the work

One component, two mount points, one aggregation endpoint returning per-vendor rollups so the
table does not issue a query per row. The API stays read-only; this is a read.

## Feature 2 — test signals, in two tiers

**Owner ruling, 2026-08-23: both, staged.** Tier 1 ships first because it needs no credential.

### Tier 1 — re-run the Signal stage. No credential, no spend.

Refetch the manifest, parse it, refetch the specification, diff against the staged copy with
oasdiff. Every part of this machinery exists; what is missing is an on-demand trigger from the
console, which is the same shape as the per-stage run buttons already planned in
`2026-08-19-a-run-button-per-stage.md`.

- **Gives** specification freshness, structural drift since the last scan, watchability.
- **Cannot give** latency, token cost or live error rate. Nothing is called, so there is nothing
  to time or bill. Saying otherwise would be the dishonesty the product exists to prevent.
- **Rung** `static` or `resolved`. Nothing was observed.
- **Auto-emit** a structural break becomes a `vendor_change`, which detectors already turn into a
  `finding`. The existing path, triggered on demand rather than on schedule.

### Tier 2 — call the vendor's API. Credential, confirm-gated.

This extends the pattern `runner/provider.py` established for model spend and the owner ratified
on 2026-08-19: unconfigured is a **state rather than an error**; the key is **read, never held**;
`require_provider` refuses *before* spending rather than after failing.

- **Owner ruling, 2026-08-23: any key, with a confirm.** Sandbox-only was offered and declined.
  That makes the confirmation the only thing between a misconfigured production key and real
  money, so it is specified accordingly: it names the vendor, it is **un-defaultable** — no
  "don't ask again" — and the run is recorded with who ran it and when.
- **Gives** latency, status class, token cost.
- **Rung** `observed`.

### The constraint that is easy to miss and expensive to get wrong

A Tier 2 run produces an observation that **Sync itself caused**. If it lands in `observed_call`
unmarked, the graph will claim a customer's users exercised an endpoint that only our test button
touched — and every rate, denominator and volume figure downstream inherits that fiction.
`observed_error_window` already carries a `source` column; `observed_call` does not. **A test run
must be attributable to the test, or it poisons the telemetry it was meant to inform.**

## Feature 3 — the improvement loop

### On CAP

CAP governs distributed data stores under partition and does not describe making an integration
faster or cheaper. What does apply — and is what the request is reaching for — is the **three-way
trade**: an eval loop that optimises one of speed, cost or accuracy will quietly spend the other
two unless all three are scored on the same run. `Axis.over(numerator, denominator)` already
enforces a denominator, which is what stops "we got faster" concealing "we got faster by doing
less".

**So: an improvement is accepted only when all three axes are scored and none regresses.** That
single rule is what separates a continuous-improvement loop from a benchmark that drifts.

### The flow

1. A test run — Tier 1 or Tier 2 — produces measurements.
2. The operator sends them to the Solution workflow with an intent: reduce latency, reduce token
   cost, improve accuracy.
3. **Precedent** supplies the vendor's specification slice and changelog at a pinned hash, each
   fact carrying its evidence rung. This is Track B, and it is the part that stops the agent
   proposing a change against an API that does not exist.
4. The agent proposes a change.
5. The eval re-runs. Accept only if all three axes hold or improve.

### The schema decision this forces

`remediation_ticket.finding_id` is `NOT NULL`. An improvement request is not a finding — nothing
detected it, and it names an aspiration rather than a defect. Minting a synthetic finding to carry
one would corrupt the finding count, which is a number the console reports and the product's
credibility rests on. **Improvements want their own row, or a nullable `finding_id` with a
`kind` that distinguishes the two.** Recommendation: a separate table, because the two have
different lifecycles and only one of them can be dismissed.

## Sequence

Feature 1 is independent of everything and can start immediately. Feature 2 Tier 1 depends on
nothing new. Feature 2 Tier 2 depends on the credential work. Feature 3 depends on Track B
(Precedent) for its evidence, and on Feature 2 for its measurements.

1. **F1** the strip — aggregation endpoint, component, five guards, two mount points.
2. **F2.1** the spec re-run trigger, reusing the run-button shape.
3. **F2.2** the credentialed tier behind `require_vendor_provider`, plus the test-run source marker.
4. **F3** the eval generalisation and the improvement row.
