/**
 * The Overview's totals line: two counts about the codebase this screen is about.
 *
 * Adopted from Lane F, which is retired. Its composition is kept — a dense line of totals above
 * the per-vendor cards — and three of its claims are not, because no payload backs them.
 *
 * **There is no time range here.** The adopted file carried a selector with four windows and no
 * query behind any of them: changing it changed nothing, while implying every figure beside it
 * was scoped to the window shown. Call sites are the current state of the index rather than
 * events in a period, so no window applies to them at all. A control that filters nothing is
 * worse than an absent one, because a reader believes it.
 *
 * **There is no active-run count.** `CLAUDE.md` is explicit that nothing in this data separates a
 * run parked on the customer's CI from one that has died, which is why there is no dot anywhere
 * in this console. A count captioned *active* makes the same claim in words.
 *
 * **A total nobody answered is `null`, never nought.** The adopted file defaulted both counts to
 * zero, so a pending answer read as a confirmed none. `findingsAreFloor` carries
 * `OverviewResponse.total_findings_bound_reached`: past the bound the count is a floor and not the
 * population, and printing it plain would overstate what was actually counted.
 */

import { Absent } from "@/components/status"

export interface TotalsBarProps {
  /** `null` when the scoped answer has not arrived. Never defaulted to a count of nought. */
  readonly totalCallSites: number | null
  readonly totalFindings: number | null
  /** Whether `totalFindings` stopped at the route's bound, making it a floor. */
  readonly findingsAreFloor: boolean
}

function Total({ value, label, floor }: { value: number | null; label: string; floor?: boolean }) {
  return (
    <div className="flex items-baseline gap-row">
      <span className="font-mono text-meta font-semibold tracking-tight text-foreground">
        {value === null ? <Absent /> : `${floor ? "at least " : ""}${value.toLocaleString()}`}
      </span>
      <span className="text-meta text-muted-foreground">{label}</span>
    </div>
  )
}

export function TotalsBar({ totalCallSites, totalFindings, findingsAreFloor }: TotalsBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-section rounded-surface border border-border bg-card px-section py-row">
      <Total value={totalCallSites} label="call sites indexed" />
      <div className="h-4 w-px bg-border" />
      <Total value={totalFindings} label="open findings" floor={findingsAreFloor} />
    </div>
  )
}
