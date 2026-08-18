/**
 * One vendor as a card: who it is, which adapter serves it, what that adapter has delivered, and
 * how much is open against it.
 *
 * **Identity is the vendor id. The mark beside it is an aid to finding the card, not the
 * identity.** This card refused to show a mark at all, reasoning that Sync holds no image and no
 * brand colour for a vendor. Owner decision 6 overruled that: marks are shown, small, fetched.
 * The part of the refusal the decision keeps is kept literally — nothing is redrawn, and a vendor
 * with no mark at the endpoint gets letters rather than an approximation. `vendor-mark.tsx`
 * carries the rest, including what the fetch discloses and how to turn it off.
 *
 * **The tier vocabulary is the registry's.** `sync/signals/registry.py` constructs
 * `RegisteredAdapter` with `coded`, `generated` or `mcp`, and `sync/dashboard/adapters.py` adds
 * `unregistered` for history keyed by a vendor id nothing serves any more. The information-
 * architecture plan writes the vocabulary as `coded / configured / generated`; `configured` is in
 * no payload and is not rendered here. A screen inventing a fourth tier is the same defect as a
 * screen inventing a number — a claim about the deployment which nothing computed.
 *
 * **The tier badge is monochrome on purpose.** Colour on this console carries a change kind, a
 * rung, or a run outcome, and a tier is none of the three: `coded` is not better than `generated`,
 * and a palette across the four would read as a quality ordering that nothing measured.
 *
 * **There is no freshness figure, because nothing measures freshness.** `last_change_at` is the
 * newest row the graph holds, not the last time the adapter was asked — nothing records an intake
 * attempt, only its result (`sync/dashboard/adapters.py`). So the card names the timestamp for what
 * it is and states the limit on screen rather than deriving a staleness verdict from it. `B136` is
 * the intake attempt record that would make a real freshness answer possible.
 */

import type { ReactNode } from "react"

import type { AdapterRow } from "@/api/types"
import { FactList, type Fact } from "@/components/fact-list"
import { Absent, Formatted } from "@/components/status"
import { NEVER_DELIVERED_NOTE } from "@/features/settings/adapter-table"
import { VendorMark } from "@/features/vendors/vendor-mark"
import { formatTimestamp, orAbsent } from "@/lib/format"
import { Badge } from "@/vendor/supabase/ui/badge"

/**
 * Every tier `GET /api/adapters` can carry, in the order the registry builds them.
 *
 * Exported so a page rendering a filter over tiers takes the payload's vocabulary rather than
 * writing its own, and so a test can prove the set has not drifted from the registry.
 */
export const ADAPTER_TIERS: readonly AdapterRow["kind"][] = [
  "coded",
  "generated",
  "mcp",
  "unregistered",
]

/**
 * The badge's whole text. The word is the channel; a colour, if one ever arrives, is a second one.
 *
 * Prefixed rather than bare because `coded` alone on a vendor card reads as a property of the
 * vendor. It is a property of what serves it.
 */
export function adapterTierLabel(kind: AdapterRow["kind"]): string {
  return `adapter: ${kind}`
}

/** A vendor the overview names and the adapter inventory does not. Not the same as never delivering. */
export const NO_ADAPTER_ROW_NOTE = "the adapter inventory carries no row for this vendor"

/** No count was computed for this vendor in this scope. Not the same as a count of nought. */
export const NO_FINDING_COUNT_NOTE = "no finding count was computed for this vendor in this scope"

/** Why a coded adapter has no source, said as the fact it is rather than as an absence. */
export const CODED_SOURCE_NOTE = "written in this repository"

/** What the timestamp above it does and does not mean. Never shortened into a label. */
export const FRESHNESS_QUALIFICATION =
  "The newest change the graph holds, not the last time the adapter was asked — nothing records " +
  "an intake attempt, only its result."

function servedFrom(adapter: AdapterRow): ReactNode {
  if (adapter.kind === "coded" && adapter.source === null) {
    return CODED_SOURCE_NOTE
  }
  return (
    <span className="font-mono text-meta">
      <Formatted value={orAbsent(adapter.source)} />
    </span>
  )
}

function intakeFacts(adapter: AdapterRow): Fact[] {
  // `null` is the graph holding no `vendor_change` row at all; `0` would be a read that found
  // nothing to say. The row switches on the distinction once rather than each cell defending
  // itself, which is the shape `features/settings/adapter-table.tsx` settled on for the same reason.
  if (adapter.changes === null) {
    return [{ label: "Adapter intake", value: NEVER_DELIVERED_NOTE }]
  }

  return [
    { label: "Changes recorded", value: <span className="font-mono">{adapter.changes}</span> },
    { label: "Operations named", value: <span className="font-mono">{adapter.operations}</span> },
    {
      label: "Newest change recorded",
      value: (
        <span className="font-mono text-meta">
          <Formatted value={formatTimestamp(adapter.last_change_at)} />
        </span>
      ),
    },
  ]
}

export interface VendorCardProps {
  /** The vendor id, which is the whole of the identity Sync holds. */
  vendorId: string
  /** This vendor's row in `GET /api/adapters`, or `null` when the inventory carries none. */
  adapter: AdapterRow | null
  /**
   * Open findings against this vendor in the scope the caller is rendering, from
   * `OverviewResponse.vendors`, or `null` when that answer does not cover this vendor.
   *
   * Nullable because the two payloads have different scopes: the adapter inventory is
   * deployment-wide and the overview is one repository, so an adapter registered but not bound in
   * the selected codebase legitimately has no count. `0` and `null` are different answers.
   */
  openFindingCount: number | null
}

export function VendorCard({ vendorId, adapter, openFindingCount }: VendorCardProps) {
  const facts: Fact[] = [
    ...(adapter === null ? [] : [{ label: "Served from", value: servedFrom(adapter) }]),
    ...(adapter === null ? [] : intakeFacts(adapter)),
    {
      label: "Open findings",
      value:
        openFindingCount === null ? (
          <Absent>
            <span className="text-meta">{NO_FINDING_COUNT_NOTE}</span>
          </Absent>
        ) : (
          <span className="font-mono">{openFindingCount}</span>
        ),
    },
  ]

  const showsTimestamp = adapter !== null && adapter.changes !== null

  return (
    <article className="flex min-w-0 flex-col gap-section rounded-surface border border-line bg-surface p-section">
      <header className="flex min-w-0 flex-wrap items-center gap-section">
        <VendorMark vendorId={vendorId} />
        <h3 className="min-w-0 font-mono text-emphasis break-words">{vendorId}</h3>
        {adapter === null ? (
          <span className="text-meta">
            <Absent>
              <span>{NO_ADAPTER_ROW_NOTE}</span>
            </Absent>
          </span>
        ) : (
          <Badge>{adapterTierLabel(adapter.kind)}</Badge>
        )}
      </header>

      <FactList facts={facts} />

      {showsTimestamp && (
        <p className="text-meta text-ink-muted leading-relaxed">{FRESHNESS_QUALIFICATION}</p>
      )}
    </article>
  )
}
