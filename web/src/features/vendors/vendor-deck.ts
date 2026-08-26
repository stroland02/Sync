/**
 * One card's worth of facts about one integration, derived from the two answers the screen holds.
 *
 * The deck is cards only (owner ruling, 2026-08-26: *"Vendors should fully switch to cards"*), and
 * a card is a small dense object — which makes every `?? 0` on the way here a claim nobody
 * measured. So the derivation is a pure function with its own test rather than eleven expressions
 * inlined into JSX: `web/CLAUDE.md` scopes the console's tests to classification and derivation,
 * and this is the derivation.
 *
 * **Two fields are nullable and neither null is a zero.**
 *
 * - `operations` — how many of the vendor's operations this repository calls, counted over
 *   `by_operation`. `null` where the coverage answer named none: the route builds `by_vendor` and
 *   `by_operation` from one read, so a vendor with call sites and no operation row is the answer
 *   being narrower than the count beside it, not a vendor whose calls reach nothing.
 * - `lastIndexed` — the newest `indexed_at` among the vendor's call sites. Staleness, never a
 *   promise the index is current.
 *
 * **Ordering is the screen's, not the payload's.** `by_vendor` is a JSON object and key order is
 * not a fact a reader should have to trust, so the deck sorts busiest first and breaks ties on the
 * id — the same ordering the retired table used, kept so the cards are not a reshuffle.
 */

import type { AdapterRow, IndexCoverageResponse } from "@/api/types"
import { vendorName } from "@/features/vendors/vendor-name"

export interface DeckRow {
  /** The identity the graph holds, and what every URL and join keys on. */
  vendorId: string
  /** How a person writes it. Never empty — `vendorName` derives one for an unregistered vendor. */
  name: string
  /** Call sites this repository binds to the vendor. A measured count; the row exists because of it. */
  callSites: number
  /** ISO-8601, or `null` where the coverage answer carries no timestamp for this vendor. */
  lastIndexed: string | null
  /** Distinct operations called, or `null` where the answer named none. Never a zero. */
  operations: number | null
  /** This vendor's row in `GET /api/adapters`, or `null` when the inventory carries none. */
  adapter: AdapterRow | null
}

/**
 * The cards, in the order they are drawn.
 *
 * `adapters` is `null` when the catalogue query has not answered — the caller keeps that fact and
 * renders it per card, because "no adapter serves this vendor" and "nothing was read about this
 * vendor" are different answers and an empty array would render the first as the second.
 */
export function deckRows(
  coverage: IndexCoverageResponse,
  adapters: readonly AdapterRow[] | null,
): DeckRow[] {
  const byVendor = new Map((adapters ?? []).map((adapter) => [adapter.vendor_id, adapter]))

  return Object.entries(coverage.by_vendor)
    .map(([vendorId, callSites]) => ({
      vendorId,
      name: vendorName(vendorId),
      callSites: Number(callSites),
      lastIndexed: coverage.last_indexed[vendorId] ?? null,
      operations: countOrNull(
        coverage.by_operation.filter((row) => row.vendor_id === vendorId).map((row) => row.operation_id),
      ),
      adapter: byVendor.get(vendorId) ?? null,
    }))
    .sort((a, b) => b.callSites - a.callSites || a.vendorId.localeCompare(b.vendorId))
}

/** Distinct members, or `null` for none — so a caller cannot render "nothing named" as a zero. */
function countOrNull(values: readonly string[]): number | null {
  const distinct = new Set(values)
  return distinct.size === 0 ? null : distinct.size
}

/**
 * Whether a card survives the search box.
 *
 * Both the id and the written name, because a reader typing "open" is looking for `openai` and a
 * reader typing "Hugging" is looking for `huggingface` — the two spellings are far enough apart
 * that matching only one would make the box look broken on whichever the reader tried.
 */
export function matchesSearch(row: DeckRow, query: string): boolean {
  const needle = query.trim().toLowerCase()
  if (needle === "") return true
  return row.vendorId.toLowerCase().includes(needle) || row.name.toLowerCase().includes(needle)
}

/** The newest call site the index wrote in this repository, or `null` if it recorded no time. */
export function newestIndexed(rows: readonly DeckRow[]): string | null {
  let newest: string | null = null
  for (const row of rows) {
    if (row.lastIndexed === null) continue
    if (newest === null || row.lastIndexed > newest) newest = row.lastIndexed
  }
  return newest
}

/**
 * The products this repository calls under one vendor, named.
 *
 * A separate walk rather than a field on `DeckRow` because the deck holds thirty rows and only the
 * open one needs the names — the count is what a card can show, and the list is what a drawer is
 * for.
 */
export function productsFor(
  coverage: IndexCoverageResponse,
  vendorId: string,
): string[] {
  const named = new Set(
    coverage.by_service
      .filter((row) => row.vendor_id === vendorId && row.service_id !== null)
      .map((row) => row.service_id as string),
  )
  return [...named].sort()
}
