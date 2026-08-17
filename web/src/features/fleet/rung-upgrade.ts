/**
 * The provenance rung, derived as a path with a next step rather than a label.
 *
 * **Why this exists, and it is a product argument rather than a presentation one.** Sync shows real
 * findings before anything is configured, because the static rung is read out of source code. A
 * telemetry product cannot do that: its dashboard is empty until traces arrive. That difference is
 * only visible if the screen says what the current evidence rests on *and* what the next rung would
 * take — so the rung is rendered as `static now, observed once you attach telemetry`, and the panel
 * shows what that bought by counting again afterwards.
 *
 * **Nothing here predicts.** There is no estimate of how many bindings would upgrade, because
 * nothing in the graph supports one. The counts are what each rung holds now; attaching telemetry
 * changes them and the same panel shows the difference. A forecast would be the composite-score
 * failure this console exists to replace, wearing a different hat.
 *
 * **Two of the five rungs are not steps.** `unresolved` is the named absence of a binding and
 * `unattributed` is a row written before the column existed. Neither is something an operator can
 * do, so neither belongs on the path — and neither is hidden either, because then the rungs on
 * screen would not add up to the total.
 */

import { type BindingSource, type DetectorRow } from "@/api/types"

/** The three rungs that are evidence, weakest first. */
export const UPGRADE_PATH = ["static", "resolved", "observed"] as const

export type UpgradeRung = (typeof UPGRADE_PATH)[number]

export interface RungStep {
  rung: UpgradeRung
  count: number
  /** Whether anything in this scope actually rests on this rung. A measured zero, not an absence. */
  reached: boolean
}

/** The rungs that carry a count but are not steps anybody can take. */
const OFF_PATH: readonly BindingSource[] = ["unresolved", "unattributed"]

function total(detectors: readonly DetectorRow[], rung: string): number {
  return detectors.reduce((sum, row) => sum + (row.by_rung[rung] ?? 0), 0)
}

export function rungSteps(detectors: readonly DetectorRow[]): RungStep[] {
  return UPGRADE_PATH.map((rung) => {
    const count = total(detectors, rung)
    return { rung, count, reached: count > 0 }
  })
}

/**
 * The weakest rung nothing rests on yet, or `null` once the strongest is reached.
 *
 * `null` is the honest answer at the top of the path: there is no further step, so the panel has
 * nothing to offer and says so rather than inventing one.
 */
export function nextStep(steps: readonly RungStep[]): RungStep | null {
  return steps.find((step) => !step.reached) ?? null
}

/** The off-path rungs holding something, in vocabulary order. Ones holding nothing are omitted. */
export function offPath(
  detectors: readonly DetectorRow[]
): { rung: BindingSource; count: number }[] {
  return OFF_PATH.map((rung) => ({ rung, count: total(detectors, rung) })).filter(
    (entry) => entry.count > 0
  )
}
