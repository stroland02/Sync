/**
 * The judgements the vendor record screen makes about its own payload, with no DOM in reach.
 *
 * Two rules live here because both are the kind that fails silently in a component: which
 * *nothing* a traffic figure is, and which chart form the payload can honestly draw. Encoded as
 * derivations so `vendor-record.test.ts` can hold them without asserting on markup.
 */

import type {
  VendorChangeRow,
  VendorChangeVolumeResponse,
  VendorOperationExposure,
} from "@/api/types"

/** Traffic across a vendor's operations: a count with its denominator, or which nothing it is. */
export type TrafficSummary =
  | { readonly kind: "counted"; readonly confirmed: number; readonly total: number }
  | { readonly kind: "never-measured"; readonly why: string }
  | { readonly kind: "no-operations"; readonly why: string }

/**
 * How many of this vendor's operations traffic confirmed, when that question has an answer.
 *
 * **A `null` `observed` collapses the whole figure rather than counting as a nought.** One
 * unmeasured operation makes "1 of 5 confirmed" a claim about five operations of which only four
 * were looked at, and a reader cannot see which four. `VendorOperationExposure.observed` names two
 * ways a null arrives — no telemetry attached, or a question spanning repositories whose
 * attachment differs — and the sentence says which one this is.
 */
export function trafficSummary(
  operations: readonly VendorOperationExposure[],
  telemetryAttachedAt: string | null,
): TrafficSummary {
  if (operations.length === 0) {
    return {
      kind: "no-operations",
      why: "this codebase calls no operation on this vendor, so there is nothing traffic could confirm",
    }
  }
  if (operations.some((operation) => operation.observed === null)) {
    return {
      kind: "never-measured",
      why:
        telemetryAttachedAt === null
          ? "no telemetry is attached to this repository, so nobody looked"
          : "this answer spans repositories whose telemetry attachment differs, so no single answer exists",
    }
  }
  return {
    kind: "counted",
    confirmed: operations.filter((operation) => operation.observed === true).length,
    total: operations.length,
  }
}

/** Which shape the change-volume payload can actually be drawn as. */
export type PublishingForm =
  | { readonly kind: "none" }
  | { readonly kind: "kinds"; readonly period: string | null }
  | { readonly kind: "timeline"; readonly periods: number }

/**
 * The chart form, chosen from the payload rather than from the question.
 *
 * `web/CLAUDE.md`: *a chart must be able to draw its own data*. A monthly stacked bar over a single
 * bucket is one column beside a ten-member legend — measured against the seeded corpus, where every
 * vendor's changes land in one month — so a set with one period is ranked by kind instead, and a
 * counted zero is a sentence rather than an empty axis.
 */
export function publishingForm(volume: VendorChangeVolumeResponse): PublishingForm {
  if (volume.total_changes === 0) return { kind: "none" }
  if (volume.timeline.length >= 2) return { kind: "timeline", periods: volume.timeline.length }
  return { kind: "kinds", period: volume.timeline[0]?.period ?? null }
}

/** A tally as ranked rows, largest first, ties broken by name so the order is stable. */
export function rankedTally(tally: Record<string, number>): { key: string; value: number }[] {
  return Object.entries(tally)
    .map(([key, value]) => ({ key, value }))
    .sort((a, b) => b.value - a.value || a.key.localeCompare(b.key))
}

/** What `observed` says on screen, including the case where nothing looked. */
export function observedLabel(observed: boolean | null): string {
  if (observed === null) return "never measured"
  return observed ? "traffic confirmed" : "no traffic seen"
}

/**
 * A change row's identity, from its own content rather than its position.
 *
 * These rows carry no id and are recorded at-least-once, so an index into a page is not a name a
 * shared address can reproduce — paginate once and it points at a different change.
 */
export function changeKey(change: VendorChangeRow): string {
  return [
    change.published_at,
    change.change_kind,
    change.operation ?? "",
    change.path_ptr ?? "",
  ].join("|")
}

/** The two records this screen holds, and the scope each is counted in. Reading order. */
export const RECORDS = [
  {
    id: "changes",
    label: "Changes published",
    scope: (vendorId: string) =>
      `Counted over ${vendorId} and in every repository — a vendor publishes a change once, to everyone.`,
  },
  {
    id: "findings",
    label: "Open findings",
    scope: (_vendorId: string, repoId: string) =>
      `Counted in ${repoId}, and in no other repository.`,
  },
] as const

export type RecordId = (typeof RECORDS)[number]["id"]

/**
 * The record the address names, or the default.
 *
 * An unknown value falls back rather than rendering nothing: a mistyped shared address should land
 * on the default record, not on a head with no table under it.
 */
export function recordFrom(param: string | null): RecordId {
  return RECORDS.find((entry) => entry.id === param)?.id ?? "changes"
}
