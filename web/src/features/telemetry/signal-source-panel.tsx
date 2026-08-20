/**
 * The signal-source role's three panels: what traffic showed up for this repository, what
 * shape it had, and where error rates moved.
 *
 * Extracted out of what used to be the standalone `ObservedTelemetryPage`, now that the
 * Signals level (`signals-page.tsx`) is the screen this content lives on. Two of Sync's five
 * detectors raise findings from watched traffic rather than from source, and the graph holds
 * `observed_call`, `observed_shape` and `observed_error_window` for exactly that reason.
 *
 * **The honesty constraint here is sharper than on most panels.** An observed call proves a
 * call site was exercised. It does not prove the binding is correct, and it does not prove the
 * call site still exists in the source. An absence is two different facts — nobody watched, or
 * somebody watched and nothing came — and `telemetry_attached_at` is what separates them, so the
 * empty states below name which one this is rather than listing what they cannot tell apart.
 *
 * No composite figure and no chart: `observed_error_window.error_count` has no denominator in
 * its own table, a shape drift is not an error, and an error window is not a verdict. `source`
 * on a shape or error window names the *mechanism* that produced the row (`interceptor`,
 * `error-payload`, `replay`) — never a vendor's name, per `sync.graph.sources`'s own docstring
 * — so nothing here claims to know which product reported it.
 *
 * ## Ported onto the substrate by M7-W175
 *
 * `docs/superpowers/briefs/2026-08-07-substrate-signals.md` is the mapping table this port was
 * gated on. Three panels, three totals, and each total is its own panel's grain — which is why each
 * takes the figure register here. **A total of zero takes no figure at all.** Rendering `0` at the
 * largest register on the screen would draw an absence as a measured zero; the empty state beneath
 * says in words which of the two this one is.
 *
 * **No catalogue is derived from `source`.** The mechanisms it names would be the truest reading of
 * this role, and two facts refuse it: `observed_call` carries no `source` at all, so a catalogue
 * built from the other two tables would imply the calls came from nowhere; and the rows here are
 * one page of each table, so a set of distinct sources read off them is a fact about the page
 * wearing the clothes of a fact about the deployment. Ruling 12.
 */

import { DEFAULT_LIMIT } from "@/api/client"
import { useRepositoryObserved } from "@/api/queries"
import { MetricPanel } from "@/components/metric-panel"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { ErrorWindowsTable } from "@/features/telemetry/error-windows-table"
import { ObservedCallsTable } from "@/features/telemetry/observed-calls-table"
import { ObservedShapesTable } from "@/features/telemetry/observed-shapes-table"
import { FooterBar } from "@/layouts/footer-bar"
import { formatTimestamp } from "@/lib/format"
import { useOffsetParam } from "@/lib/use-offset-param"

/**
 * Telemetry attached and quiet: the panel-by-panel nothing, which is a measured nought.
 *
 * `telemetry_attached_at` is what separates this from never-watched (`B157`). Once a source is
 * attached the three panels genuinely differ — calls can arrive while no error window does — so
 * each states its own absence. The never-attached case is one fact about the repository rather
 * than three about the panels, and `NeverAttached` below is where it is said once.
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
 * Nothing ever watched this repository, said once for the whole role.
 *
 * **This replaced three identical copies of itself.** Each of the three panels rendered the same
 * paragraph whenever `telemetry_attached_at` was null — which is every deployment that has not
 * attached a source, so the common case drew one fact three times, verbatim, and the role's card
 * became a wall of repeated prose with no data in it. Nothing is lost by saying it once: the
 * sentence names all three things that would have been recorded, so a reader still learns what
 * telemetry holds from a screen that has none.
 *
 * It names the command, as every empty state here does since `CI-W514`. A reader told they have no
 * telemetry and not how to attach any has been given a diagnosis and no next step, and this is the
 * one empty state on the level whose remedy is a command rather than a wait.
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

/** A total at the figure register, or nothing at all when the total is zero. */
function countMetric(total: number, unit: string) {
  return total === 0 ? undefined : { value: total.toLocaleString(), unit }
}

export function SignalSourcePanel({ repoId }: { repoId: string }) {
  const [callsOffset, setCallsOffset] = useOffsetParam("calls_offset")
  const [shapesOffset, setShapesOffset] = useOffsetParam("shapes_offset")
  const [errorWindowsOffset, setErrorWindowsOffset] = useOffsetParam("error_windows_offset")
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

  // Said once for the whole role rather than once per panel. Three panels each reporting that
  // nobody ever watched is one fact about the repository written three times, and the three
  // panels below have nothing to distinguish until a source exists to distinguish them.
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
          <>
            <ObservedCallsTable calls={calls.items} />
            <FooterBar
              offset={callsOffset}
              limit={DEFAULT_LIMIT}
              shown={calls.items.length}
              total={calls.total}
              nextOffset={calls.next_offset}
              busy={query.isFetching}
              onOffsetChange={setCallsOffset}
            />
          </>
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
          <>
            <ObservedShapesTable shapes={shapes.items} />
            <FooterBar
              offset={shapesOffset}
              limit={DEFAULT_LIMIT}
              shown={shapes.items.length}
              total={shapes.total}
              nextOffset={shapes.next_offset}
              busy={query.isFetching}
              onOffsetChange={setShapesOffset}
            />
          </>
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
          <>
            <ErrorWindowsTable windows={error_windows.items} />
            <FooterBar
              offset={errorWindowsOffset}
              limit={DEFAULT_LIMIT}
              shown={error_windows.items.length}
              total={error_windows.total}
              nextOffset={error_windows.next_offset}
              busy={query.isFetching}
              onOffsetChange={setErrorWindowsOffset}
            />
          </>
        )}
      </MetricPanel>
    </div>
  )
}
