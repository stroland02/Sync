/**
 * The signal-source role's three panels: what traffic showed up for this repository, what
 * shape it had, and where error rates moved.
 *
 * No composite figure and no chart — `observed_error_window.error_count` has no denominator in its
 * own table, and an error window is not a verdict. No catalogue is derived from `source` either
 * (Ruling 12): `observed_call` carries none, and these rows are one page of each table, so distinct
 * sources read off them would be a fact about the page rather than the deployment.
 *
 * Each panel heading is the word `signals-page.tsx`'s pager bar uses for its set, so a rename here
 * is a rename there; the offsets stay here because they are this read's parameters.
 */

import { DEFAULT_LIMIT } from "@/api/client"
import { useRepositoryObserved } from "@/api/queries"
import { MetricPanel } from "@/components/metric-panel"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { ErrorWindowsTable } from "@/features/telemetry/error-windows-table"
import { ObservedCallsTable } from "@/features/telemetry/observed-calls-table"
import { ObservedShapesTable } from "@/features/telemetry/observed-shapes-table"
import { formatTimestamp } from "@/lib/format"
import { useOffsetParam } from "@/lib/use-offset-param"

/**
 * Telemetry attached and quiet: the panel-by-panel nothing, which is a measured nought.
 *
 * `telemetry_attached_at` is what separates this from never-watched (`B157`); once a source is
 * attached the three panels genuinely differ, since calls can arrive while no error window does.
 */
function nothingArrived(what: string, repoId: string, attachedAt: string) {
  return {
    headline: `Telemetry is attached, and no ${what} arrived.`,
    detail:
      `Traffic has been watched for ${repoId} since ${formatTimestamp(attachedAt)}, and nothing ` +
      "arrived in the window this answer covers. That is a measured nought: the call sites the " +
      "index found were not exercised, rather than not looked at.",
  }
}

/**
 * Nothing ever watched this repository, said once for the whole role rather than once per panel.
 *
 * It names the command, as every empty state here does since `CI-W514`.
 */
function NeverAttached() {
  return (
    <EmptyState
      headline="Telemetry was never attached to this repository."
      detail={
        "Nothing has watched this repository's traffic, so there are no observed calls, response " +
        "shapes or error windows to have recorded. This is the absence of a measurement rather " +
        "than a measurement of nought — no call site here has been shown unexercised, only " +
        "unwatched."
      }
      command="uv run sync ingest --repo-id <repo> --vendor <vendor> --payload <otlp.json>"
    />
  )
}

/** No figure at all when the total is zero: a rendered `0` draws an absence as a measured nought. */
function countMetric(total: number, unit: string) {
  return total === 0 ? undefined : { value: total.toLocaleString(), unit }
}

export function SignalSourcePanel({ repoId }: { repoId: string }) {
  const [callsOffset] = useOffsetParam("calls_offset")
  const [shapesOffset] = useOffsetParam("shapes_offset")
  const [errorWindowsOffset] = useOffsetParam("error_windows_offset")
  const query = useRepositoryObserved(repoId, {
    callsLimit: DEFAULT_LIMIT,
    callsOffset,
    shapesLimit: DEFAULT_LIMIT,
    shapesOffset,
    errorWindowsLimit: DEFAULT_LIMIT,
    errorWindowsOffset,
  })

  if (query.isPending) return <LoadingState what={`observed telemetry for ${repoId}`} />
  if (query.isError) {
    return <ErrorState error={query.error} what={`observed telemetry for ${repoId}`} onRetry={() => void query.refetch()} />
  }

  const { calls, shapes, error_windows, telemetry_attached_at } = query.data

  if (telemetry_attached_at === null) return <NeverAttached />

  return (
    <div className="flex min-w-0 flex-col gap-section">
      <MetricPanel
        label="Observed calls"
        metric={countMetric(calls.total, `call${calls.total === 1 ? "" : "s"} observed`)}
        caption={
          <p className="max-w-prose">
            One row per unit of work's use of one vendor operation. A row proves the call ran at
            least once; it does not prove the operation it names is the operation that was actually
            called — that is what the rung says.
          </p>
        }
      >
        {calls.total === 0 ? (
          <EmptyState {...nothingArrived("observed calls", repoId, telemetry_attached_at)} />
        ) : (
          <ObservedCallsTable calls={calls.items} />
        )}
      </MetricPanel>

      <MetricPanel
        label="Response shapes"
        metric={countMetric(shapes.total, `field shape${shapes.total === 1 ? "" : "s"} seen`)}
        caption={
          <p className="max-w-prose">
            What the operations this repository's own traffic names have actually been seen to
            return, joined in through those operations rather than stored per repository — a shape
            is a fact about the vendor, not about who calls it.
          </p>
        }
      >
        {shapes.total === 0 ? (
          <EmptyState {...nothingArrived("response shapes", repoId, telemetry_attached_at)} />
        ) : (
          <ObservedShapesTable shapes={shapes.items} />
        )}
      </MetricPanel>

      <MetricPanel
        label="Error windows"
        metric={countMetric(
          error_windows.total,
          `window${error_windows.total === 1 ? "" : "s"} recorded`,
        )}
        caption={
          <p className="max-w-prose">
            How many times one operation failed, over a window an error tracker recorded. A count
            here has no denominator and is not a rate — it says nothing on its own about whether
            traffic is getting worse, only how many failures one window held.
          </p>
        }
      >
        {error_windows.total === 0 ? (
          <EmptyState {...nothingArrived("error windows", repoId, telemetry_attached_at)} />
        ) : (
          <ErrorWindowsTable windows={error_windows.items} />
        )}
      </MetricPanel>
    </div>
  )
}
