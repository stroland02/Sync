/**
 * Metrics → Corpus: how well the remediation loop actually works, and which parts of that
 * question have no answer yet.
 *
 * **Owner ruling, 2026-08-19:** `/api/corpus/health` becomes a fourth Metrics tab. The route and
 * its view model have existed since `M12-W323` with nothing rendering them, and the payload is
 * the most console-shaped one in the product — every axis arrives carrying `status`,
 * `has_samples`, `sample_count`, `provenance` and its own `denominator_description`, which is the
 * absence-versus-zero distinction computed server-side rather than asserted here.
 *
 * **This screen is the product's argument in its most literal form.** Measured against this
 * deployment today: five axes, all `unmeasured`, zero samples. A competing tool with this data
 * would show a merge rate of 100% over one attempt, or a green tick, or nothing at all. What this
 * screen shows is five named measurements, each with the denominator it would need, and the
 * statement that none of them has a sample yet. **An unmeasured axis is not a failing axis and
 * this screen never renders it as one** — no red, no warning, no "incomplete" badge. It is a
 * measurement nobody has been able to take, which is a fact about how much Sync has run rather
 * than about how well it works.
 *
 * **No aggregate over the axes, and this is where one would be most tempting.** Five ratios with
 * a shared subject is exactly the shape that invites a "corpus health score", and the payload
 * even offers `axes_measured_count` to build one from. A scalar averaging a merge rate, a routing
 * accuracy and a token cost would collapse three incommensurable things, and averaging *measured
 * and unmeasured* would put "we could not check" on the same axis as "we checked and it passed" —
 * the exact failure `CLAUDE.md` says this console exists to replace. The counts are reported as
 * counts.
 *
 * **A ratio is rendered with its denominator, always.** `denominator_description` is on the
 * payload for that reason, and it is rendered beside every value rather than behind a tooltip: a
 * merge rate whose denominator a reader cannot see is a number they cannot check.
 */

import { useQuery } from "@tanstack/react-query"

import {
  ApiStatusError,
  MalformedResponseError,
  UnreachableApiError,
} from "@/api/errors"
import { InfoHint } from "@/components/info-hint"
import { CORPUS_SCOPE, ScopeChip } from "@/components/scope-chip"
import { KpiStrip } from "@/components/kpi-strip"
import { MetricPanel } from "@/components/metric-panel"
import { Absent } from "@/components/status"
import { ErrorState, LoadingState } from "@/components/states"
import { PageTabs, solutionsTabs } from "@/components/page-tabs"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { UnknownRoute } from "@/layouts/unknown-route"
import { useParams } from "react-router"

interface Axis {
  name: string
  display_name: string
  status: "measured" | "unmeasured"
  has_samples: boolean
  sample_count: number
  provenance: string
  value: number | Record<string, number | null> | null
  groups?: Record<string, { value: number | null; n: number; has_samples: boolean }>
  unit: string
  denominator_description: string
}

interface CorpusHealth {
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

async function fetchCorpusHealth(signal?: AbortSignal): Promise<CorpusHealth> {
  const path = "/api/corpus/health"
  let response: Response
  try {
    response = await fetch(path, { headers: { Accept: "application/json" }, signal })
  } catch (cause) {
    if (signal?.aborted) throw cause
    throw new UnreachableApiError(path, { cause })
  }
  if (!response.ok) throw new ApiStatusError(response.status, path)
  try {
    return (await response.json()) as CorpusHealth
  } catch (cause) {
    throw new MalformedResponseError(path, { cause })
  }
}

/** A ratio as a percentage, a duration as seconds, a token count as itself. */
function formatValue(value: number, unit: string): string {
  if (unit === "ratio") return `${Math.round(value * 100)}%`
  if (unit === "milliseconds") return `${(value / 1000).toFixed(1)}s`
  return value.toLocaleString()
}

function AxisPanel({ axis }: { axis: Axis }) {
  const grouped = axis.groups !== undefined && Object.keys(axis.groups).length > 0

  return (
    <div className="flex min-w-0 flex-col gap-row rounded-surface border border-line bg-surface p-section">
      <div className="flex flex-col gap-field">
        <h3 className="text-section">{axis.display_name}</h3>
        {/* The denominator is on screen rather than in a tooltip: a ratio whose denominator a
            reader cannot see is a number they cannot check. */}
        <p className="max-w-prose text-meta text-ink-muted">
          Measured over {axis.denominator_description}.
        </p>
      </div>

      {axis.status === "unmeasured" ? (
        // Never "failing", never "0%". An axis with no samples is a measurement nobody could
        // take -- a fact about how much has run, not a result -- and the panel's hint carries why.
        <span className="text-body">
          <Absent>not measured yet</Absent>
        </span>
      ) : grouped ? (
        <div className="flex flex-col gap-field">
          {Object.entries(axis.groups!).map(([group, entry]) => (
            <div key={group} className="flex items-baseline justify-between gap-section">
              <span className="min-w-0 truncate font-mono text-meta text-ink">{group}</span>
              <span className="shrink-0 text-meta tabular-nums text-ink-muted">
                {entry.has_samples && entry.value !== null ? (
                  <>
                    {formatValue(entry.value, axis.unit)}{" "}
                    <span className="text-ink-muted">over {entry.n.toLocaleString()}</span>
                  </>
                ) : (
                  <Absent>no sample</Absent>
                )}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex items-baseline gap-row">
          <span className="text-figure tabular-nums text-foreground">
            {typeof axis.value === "number" ? formatValue(axis.value, axis.unit) : "—"}
          </span>
          <span className="text-meta text-ink-muted">
            over {axis.sample_count.toLocaleString()} sample
            {axis.sample_count === 1 ? "" : "s"}
          </span>
        </div>
      )}
    </div>
  )
}

export function CorpusPage() {
  const { repoId } = useParams<{ repoId: string }>()
  const query = useQuery({
    queryKey: ["corpus-health"],
    queryFn: ({ signal }) => fetchCorpusHealth(signal),
  })

  if (repoId === undefined) return <UnknownRoute />

  return (
    <section className="flex flex-col gap-8">
      <Breadcrumbs trail={[{ label: "Solutions" }]} />
      <PageTabs label="Solutions" tabs={solutionsTabs(repoId)} />

      {query.isPending && <LoadingState what="the corpus evidence" />}
      {query.isError && (
        <ErrorState
          error={query.error}
          what="the corpus evidence"
          onRetry={() => void query.refetch()}
        />
      )}

      {query.isSuccess && (
        <>
          <KpiStrip
            items={[
              {
                label: "Axes measured",
                // Two counts side by side, never a ratio: "2 of 5 measured" as a percentage
                // would read as a score of the product rather than a count of what has run.
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

          <div className="flex items-center gap-row">
            <h2 className="text-section">Quality axes</h2>
            <ScopeChip scope="all workspaces">{CORPUS_SCOPE}</ScopeChip>
            <InfoHint label="About corpus evidence">
              The quality axes Sync measures itself against, computed over{" "}
              <code className="font-mono">migration_outcome</code> — one row per repair attempt,
              not per finding. There is deliberately no combined score: a figure averaging a merge
              rate, a routing accuracy and a token cost would collapse three incommensurable
              measurements, and averaging measured with unmeasured axes would put &ldquo;we could
              not check&rdquo; on the same axis as &ldquo;we checked and it passed&rdquo;. An axis
              with no samples is reported unmeasured rather than as nought, and each names the
              denominator it would be computed over — so what is missing is legible rather than
              merely absent.
            </InfoHint>
          </div>

          <MetricPanel
            label="By axis"
            caption="Each axis, its value, and the denominator it was computed over."
          >
            <div className="grid auto-rows-fr gap-section xl:grid-cols-2">
              {query.data.axes.map((axis) => (
                <AxisPanel key={axis.name} axis={axis} />
              ))}
            </div>
          </MetricPanel>
        </>
      )}
    </section>
  )
}
