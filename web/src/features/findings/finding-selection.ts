/**
 * Which row the URL is asking the inspector for, and whether this page holds it.
 * `features/bindings/binding-selection.ts` carries the argument for putting the drawer's open
 * state in the address bar.
 *
 * The key is matched against `change_unit_id` when grouped and `finding_id` when flat: the two
 * views hold two id spaces, and nothing stops one id appearing in both. Keys are compared whole
 * and never parsed -- a `change_unit_id` is `vendor:operation:kind` joined, and an operation may
 * itself hold a colon.
 */

import type { ChangeUnitRow, RiskRow } from "@/api/types"

/** The search parameter the inspector's open state is spelled with. */
export const INSPECT_KEY = "inspect"

export type FindingSelection =
  | { kind: "none" }
  | { kind: "unit"; unit: ChangeUnitRow }
  | { kind: "finding"; row: RiskRow }
  | { kind: "unresolved"; key: string }

/**
 * What the URL is asking for, against the rows this page actually has.
 *
 * An empty parameter reads as nothing selected rather than as a key matching nothing: the setter
 * spells the closed state as the parameter's absence, so a hand-edited `?inspect=` is the same
 * intention badly spelled and not a lookup that failed.
 */
export function selectRow(
  key: string | null,
  grouped: boolean,
  units: readonly ChangeUnitRow[],
  rows: readonly RiskRow[],
): FindingSelection {
  if (key === null || key === "") return { kind: "none" }
  if (grouped) {
    const unit = units.find((candidate) => candidate.change_unit_id === key)
    return unit === undefined ? { kind: "unresolved", key } : { kind: "unit", unit }
  }
  const row = rows.find((candidate) => candidate.finding_id === key)
  return row === undefined ? { kind: "unresolved", key } : { kind: "finding", row }
}
