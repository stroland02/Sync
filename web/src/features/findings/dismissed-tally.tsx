/**
 * Findings a human has set aside, by the reason standing against each.
 *
 * **Read-only, on the owner's ruling of 2026-08-19.** `POST /api/findings/{id}/dismissal` exists
 * and this console does not call it: dismissing stays a command-line action, and what the screen
 * owes is the standing. Without it the Findings table shows open findings and nothing else, so a
 * finding somebody deliberately set aside is indistinguishable from one nobody has looked at.
 *
 * **Counted over the latest ruling per finding, not over every row.** A finding dismissed,
 * restored and dismissed again is one dismissal now, and the store's query is what makes that
 * true — this component only has to avoid describing it as a history.
 *
 * **A reason absent from `counts` is not a reason at zero, and this renders neither as the
 * other.** The store's own docstring is explicit that it returns only reasons that occur, so a
 * bar at nought would be a claim the query cannot make. The empty case says which of the two
 * nothings it is instead of drawing an empty chart.
 *
 * **The figure is fleet-wide and says so on screen, on the Runs page's precedent.** Dismissals
 * carry a finding id and no `repo_id`, and joining back to `finding` would not recover one: that
 * table is re-derived by every scan, so a dismissal can outlive the row it names. Two responses
 * were available and this codebase has already ruled between them —
 * `sync.dashboard.fleet.abandonment_by_change_kind` has the identical problem and states its
 * fleet scope in the caption, while `RunsCard` and `PrecedentSummaryCard` stay unmounted because
 * theirs is a *page of rows* that would each read as this repository's. A distribution that names
 * its own scope is the first case, not the second.
 */

import { useQuery } from "@tanstack/react-query"

import { fetchDismissalTally } from "@/api/client"
import { InfoHint } from "@/components/info-hint"
import { MetricPanel } from "@/components/metric-panel"
import { RankedBars } from "@/components/ranked-bars"
import { ErrorState, LoadingState } from "@/components/states"

export function DismissedTally() {
  const query = useQuery({
    queryKey: ["findings", "dismissals"],
    queryFn: ({ signal }) => fetchDismissalTally(signal),
  })

  if (query.isPending) return <LoadingState what="dismissed findings" />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what="dismissed findings"
        onRetry={() => void query.refetch()}
      />
    )
  }

  const hint = (
    <InfoHint label="About dismissed findings">
      Findings a human has ruled on, counted by the reason standing against each. One finding
      counts once no matter how often the ruling has changed — this is the standing now, never a
      history. Dismissing is a command-line action; this console reads the record and does not
      write to it. A reason missing from this chart has never been used, which is a different
      claim from a reason used no times, and the query cannot make the second. This figure is
      every repository&rsquo;s and not this one&rsquo;s: a dismissal records a finding and no
      repository, and the findings table it would have to be joined against is rebuilt by every
      scan, so a dismissal can outlive the row that would have named the workspace.
    </InfoHint>
  )

  const rows = Object.entries(query.data.counts)
    .map(([key, value]) => ({ key, value }))
    .sort((a, b) => b.value - a.value || a.key.localeCompare(b.key))

  if (rows.length === 0) {
    return (
      <MetricPanel
        label="Dismissed"
        hint={hint}
        caption="Nobody has dismissed a finding in any repository this deployment holds. That is a measurement — the query ran and found no standing dismissal — rather than a screen that cannot see them."
      >
        <p className="text-body text-ink-muted">
          Every finding the graph holds stands open. A finding leaves this figure by being
          restored as well as by never having been dismissed, and those are the same nothing here.
        </p>
      </MetricPanel>
    )
  }

  return (
    <MetricPanel
      label="Dismissed"
      hint={hint}
      metric={{ value: query.data.total.toLocaleString(), unit: "findings set aside" }}
    >
      <RankedBars
        label="By reason"
        caption={`${query.data.total.toLocaleString()} findings stand dismissed across every repository this deployment holds, not in this workspace alone — a dismissal records no repository. Each bar's width is its share of the largest reason, not of the total.`}
        rows={rows}
        unit="findings"
        colourByKey={false}
      />
    </MetricPanel>
  )
}
