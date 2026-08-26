/**
 * Findings a human has set aside, by the reason standing against each — as a pane of the locked
 * Metrics grid.
 *
 * Rebuilt from `features/findings/dismissed-tally.tsx` on 2026-08-26, which this replaces. That
 * file was a `MetricPanel` mounted only here, on a screen that was one scrolling column; the
 * component is gone rather than left beside its replacement. The reads are unchanged: it still
 * asks under `useDismissalTally`'s key, which is the same key the Findings status note reads, so
 * the chart and the note cannot render two different numbers from two different answers.
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
 * other.** The store returns only reasons that occur, so a bar at nought would be a claim the
 * query cannot make. The empty case says which of the two nothings it is instead of drawing an
 * empty chart.
 *
 * **The figure is fleet-wide and the band says so.** Dismissals carry a finding id and no
 * `repo_id`, and joining back to `finding` would not recover one: that table is re-derived by
 * every scan, so a dismissal can outlive the row it names.
 */

import { Archive } from "lucide-react"

import { InfoHint } from "@/components/info-hint"
import { PanelPane } from "@/components/pane"
import { RankedBars } from "@/components/ranked-bars"
import { ErrorState, LoadingState } from "@/components/states"
import { Absent } from "@/components/status"
import { spansOrdersOfMagnitude } from "@/features/dashboards/daily-series"
import { useDismissalTally } from "@/features/findings/dismissed-note"

const HINT = (
  <InfoHint label="About dismissed findings">
    Findings a human has ruled on, counted by the reason standing against each. One finding counts
    once no matter how often the ruling has changed — this is the standing now, never a history.
    Dismissing is a command-line action; this console reads the record and does not write to it. A
    reason missing from this chart has never been used, which is a different claim from a reason
    used no times, and the query cannot make the second. This figure is every repository&rsquo;s
    and not this one&rsquo;s: a dismissal records a finding and no repository, and the findings
    table it would have to be joined against is rebuilt by every scan, so a dismissal can outlive
    the row that would have named the workspace.
  </InfoHint>
)

export function DismissedPane({ className }: { className?: string } = {}) {
  const query = useDismissalTally()

  if (query.isPending || query.isError) {
    return (
      <PanelPane
        className={className}
        label="Set aside"
        icon={Archive}
        hint={HINT}
        bodyClassName="p-section"
      >
        {query.isPending ? (
          <LoadingState what="dismissed findings" />
        ) : (
          <ErrorState
            error={query.error}
            what="dismissed findings"
            onRetry={() => void query.refetch()}
          />
        )}
      </PanelPane>
    )
  }

  const rows = Object.entries(query.data.counts)
    .map(([key, value]) => ({ key, value }))
    .sort((a, b) => b.value - a.value || a.key.localeCompare(b.key))

  return (
    <PanelPane
      className={className}
      label="Set aside"
      icon={Archive}
      hint={HINT}
      actions={
        <span className="text-meta text-ink-muted">
          <span className="font-mono tabular-nums text-ink">
            {query.data.total.toLocaleString()}
          </span>{" "}
          findings · all workspaces
        </span>
      }
      bodyClassName="p-section"
      footer={
        <span>All workspaces — a dismissal records no repository to narrow it by.</span>
      }
      footerClassName="h-auto min-h-[var(--row-lg)] items-start py-field leading-relaxed"
    >
      {rows.length === 0 ? (
        <div className="flex max-w-prose flex-col gap-field">
          <p className="text-body">
            <Absent>no standing dismissal</Absent> — the query ran and found none.
          </p>
          <p className="text-body text-ink-muted">
            Every finding the graph holds stands open. A finding leaves this figure by being
            restored as well as by never having been dismissed, and those are the same nothing
            here.
          </p>
        </div>
      ) : (
        <RankedBars
          className="h-auto rounded-none border-0 bg-transparent p-0"
          label="By reason"
          caption="Each bar's width is its share of the largest reason, not of the total. A reason with no bar has never been used, which the query cannot tell apart from a reason used no times."
          rows={rows}
          unit="findings"
          colourByKey={false}
          scale={spansOrdersOfMagnitude(rows.map((row) => row.value)) ? "log" : "linear"}
        />
      )}
    </PanelPane>
  )
}
