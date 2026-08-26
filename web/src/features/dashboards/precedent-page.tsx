/**
 * Corpus: how well the remediation loop actually works, and which parts of that question have no
 * answer yet — as a viewport-locked bento of four panes.
 *
 * **Rebuilt 2026-08-26 from a scrolling column into a locked grid.** The old screen was a headed
 * section, a five-card grid of axes, a second headed section, and two chart cards below the fold.
 * Four of those five surfaces said the same six words — *not measured yet* — and each spent a
 * border and a heading to say them. The axes are a ledger now, which puts every denominator in a
 * column beside its axis, and the three charts sit where a reader can compare them.
 *
 * **Owner ruling, 2026-08-19:** `/api/precedent/health` becomes a Metrics destination. The route
 * and its view model have existed since `M12-W323`, and the payload is the most console-shaped one
 * in the product — every axis arrives carrying `status`, `has_samples`, `sample_count`,
 * `provenance` and its own `denominator_description`, which is the absence-versus-zero distinction
 * computed server-side rather than asserted here.
 *
 * **This screen is the product's argument in its most literal form.** Measured against this
 * deployment today: five axes, all `unmeasured`, zero samples. A competing tool with this data
 * would show a merge rate of 100% over one attempt, or a green tick, or nothing at all. What this
 * screen shows is five named measurements, each with the denominator it would need, and the
 * statement that none of them has a sample yet.
 *
 * **No aggregate over the axes.** `axis-ledger.tsx` carries the argument at the surface that would
 * have to draw one.
 *
 * **Every form here is a count.** Three panes of bars and a ledger; no ring, no rate, no score.
 * `web/CLAUDE.md`'s chart law outranks the reference on this screen and nothing on it divides one
 * measurement by another.
 */

import { useQuery } from "@tanstack/react-query"
import { Ruler } from "lucide-react"
import { useParams } from "react-router"

import {
  ApiStatusError,
  MalformedResponseError,
  UnreachableApiError,
} from "@/api/errors"
import { InfoHint } from "@/components/info-hint"
import { KpiStrip } from "@/components/kpi-strip"
import { PanelPane } from "@/components/pane"
import { CORPUS_SCOPE, ScopeChip } from "@/components/scope-chip"
import { ErrorState, LoadingState } from "@/components/states"
import { AbandonReasonsPane } from "@/features/dashboards/abandon-reasons-pane"
import { AxisLedger, type Axis } from "@/features/dashboards/axis-ledger"
import { ChangeKindPane } from "@/features/dashboards/change-kind-pane"
import { TierOutcomesPane } from "@/features/dashboards/tier-outcomes-pane"
import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"
import { UnknownRoute } from "@/layouts/unknown-route"

interface PrecedentHealth {
  summary: {
    total_runs: number
    distinct_findings: number
    pull_requests_opened: number
    pull_requests_merged: number
    findings_abandoned: number
    production_attempts: number
    rehearsal_attempts: number
    axes_measured_count: number
    axes_unmeasured_count: number
    total_axes: number
    has_any_samples: boolean
  }
  axes: Axis[]
}

async function fetchPrecedentHealth(signal?: AbortSignal): Promise<PrecedentHealth> {
  const path = "/api/precedent/health"
  let response: Response
  try {
    response = await fetch(path, { headers: { Accept: "application/json" }, signal })
  } catch (cause) {
    if (signal?.aborted) throw cause
    throw new UnreachableApiError(path, { cause })
  }
  if (!response.ok) throw new ApiStatusError(response.status, path)
  try {
    return (await response.json()) as PrecedentHealth
  } catch (cause) {
    throw new MalformedResponseError(path, { cause })
  }
}

/** What the axes that have samples drew them from, or `null` when no axis has one. */
function describeProvenance(axes: readonly Axis[]): string | null {
  const sourced = [...new Set(axes.filter((axis) => axis.has_samples).map((axis) => axis.provenance))]
  // Null rather than the payload's "unmeasured": with no sample behind any axis, nothing answered
  // what the samples came from, and a word here would name a category that was never found.
  return sourced.length === 0 ? null : sourced.sort().join(", ")
}

const AXES_HINT = (
  <InfoHint label="About corpus evidence">
    The quality axes Sync measures itself against, computed over{" "}
    <code className="font-mono">migration_outcome</code> — one row per repair attempt, not per
    finding. There is deliberately no combined score: a figure averaging a merge rate, a routing
    accuracy and a token cost would collapse three incommensurable measurements, and averaging
    measured with unmeasured axes would put &ldquo;we could not check&rdquo; on the same axis as
    &ldquo;we checked and it passed&rdquo;. An axis with no samples is reported unmeasured rather
    than as nought, and each names the denominator it would be computed over — so what is missing is
    legible rather than merely absent.
  </InfoHint>
)

export function PrecedentPage() {
  const { repoId } = useParams<{ repoId: string }>()
  const query = useQuery({
    queryKey: ["corpus-health"],
    queryFn: ({ signal }) => fetchPrecedentHealth(signal),
  })

  if (repoId === undefined) return <UnknownRoute />

  // The screen states what it is showing whether or not the query has answered: a band that
  // appears only on success renders "not asked yet" and "asked and empty" as the same nothing.
  const status: StatusSegment[] = query.isSuccess
    ? [
        {
          kind: "listing",
          label: "Quality axes",
          // Two counts, never a ratio: "2 of 5" as a percentage would read as a score of the
          // product rather than a count of what has run.
          text: `${query.data.summary.axes_measured_count} of ${query.data.summary.total_axes} measured, all ${query.data.summary.total_axes} on screen.`,
        },
        {
          kind: "figure",
          label: "Provenance",
          value: describeProvenance(query.data.axes),
          scope: "all workspaces",
        },
        {
          kind: "figure",
          label: "Runs",
          value: query.data.summary.total_runs.toLocaleString(),
          scope: "all workspaces",
        },
        {
          kind: "figure",
          label: "Findings abandoned",
          value: query.data.summary.findings_abandoned.toLocaleString(),
          scope: "all workspaces",
        },
      ]
    : [
        {
          kind: "none",
          why: query.isError
            ? "the corpus evidence did not answer"
            : "asking for the corpus evidence",
        },
      ]

  return (
    <ScreenFrame
      status={status}
      layout="locked"
      subtitle="One row is one attempt, and counts once as a finding — every figure here is every workspace's, not this one's."
    >
      {query.isSuccess && (
        <KpiStrip
          items={[
            {
              label: "Axes measured",
              // Two counts side by side, never a ratio: "2 of 5 measured" as a percentage would
              // read as a score of the product rather than a count of what has run.
              value: `${query.data.summary.axes_measured_count} of ${query.data.summary.total_axes}`,
              note: "quality axes with at least one sample behind them",
              figure: false,
            },
            {
              label: "Pull requests opened",
              value: query.data.summary.pull_requests_opened.toLocaleString(),
              note: `${query.data.summary.pull_requests_merged.toLocaleString()} of them merged`,
            },
            {
              label: "Attempts recorded",
              value: query.data.summary.production_attempts.toLocaleString(),
              // One row is one attempt, not one finding -- the grain rule, on screen where a
              // reader would otherwise compare this against the findings count and be wrong.
              note: `over ${query.data.summary.distinct_findings.toLocaleString()} distinct findings — one row is one attempt`,
            },
            {
              label: "Rehearsals",
              value: query.data.summary.rehearsal_attempts.toLocaleString(),
              note: "halted before the remote, and excluded from every axis above",
            },
          ]}
        />
      )}

      {/* Row A is the ledger and the reason codes; row B is the two rankings that read against
          each other — which tier gave up and on what subject matter. `.bento-lock` supplies the
          tracks above 1024x720 and hands the grid its own scrollbar below it. */}
      <div className="bento-lock grid min-h-0 min-w-0 flex-1 grid-cols-1 gap-8 lg:grid-cols-12">
        <PanelPane
          className="lg:col-span-7"
          label="Quality axes"
          icon={Ruler}
          hint={AXES_HINT}
          actions={
            <span className="flex items-center gap-row text-meta text-ink-muted">
              <ScopeChip scope="all workspaces">{CORPUS_SCOPE}</ScopeChip>
            </span>
          }
          scroll={query.isSuccess ? false : true}
          bodyClassName={query.isSuccess ? undefined : "p-section"}
          footer={
            query.isSuccess ? (
              <span>
                {query.data.summary.axes_measured_count} of {query.data.summary.total_axes}{" "}
                measured, all {query.data.summary.total_axes} on screen — an axis with no sample is
                a measurement nobody could take, never a failing result.
              </span>
            ) : undefined
          }
          footerClassName="h-auto min-h-[var(--row-lg)] items-start py-field leading-relaxed"
        >
          {query.isPending && <LoadingState what="the corpus evidence" />}
          {query.isError && (
            <ErrorState
              error={query.error}
              what="the corpus evidence"
              onRetry={() => void query.refetch()}
            />
          )}
          {query.isSuccess && <AxisLedger axes={query.data.axes} />}
        </PanelPane>

        <AbandonReasonsPane className="lg:col-span-5" />
        <ChangeKindPane className="lg:col-span-7" />
        <TierOutcomesPane className="lg:col-span-5" />
      </div>
    </ScreenFrame>
  )
}
