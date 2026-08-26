/**
 * One integration as a card: who it is, how much of this codebase reaches it, and at which rung.
 *
 * **Owner ruling, 2026-08-26 — *"Vendors should fully switch to cards."*** The screen behind this
 * component was a hybrid: a card grid beside a four-column table of the same rows, with the table
 * still carrying eighteen references. The table is gone, so this card is now the whole row and had
 * to grow into it — the count it used to sit beside, the rung that qualifies that count, and the
 * two coverage facts (operations reached, products named) the table's columns held.
 *
 * ## The figure is qualified by a rung, and that is a rule rather than a flourish
 *
 * `CLAUDE.md` requires the rung on every binding and on everything derived from one, because a
 * false positive that cannot be attributed to a rung cannot be fixed. The number on this card is
 * *statically indexed call sites* — not calls, not traffic — and `static` is the word for that.
 * It is the same rung on every card today, which is exactly why it is drawn as a qualifier of the
 * figure rather than as a facet or a chip in the header: it says what the number is, and a reader
 * who takes the number for observed traffic has been misled by its absence. Telemetry is reported
 * on Signals, beside this rather than blended into it.
 *
 * ## Identity is the vendor id. The mark and the name are aids to finding it
 *
 * `vendor-mark.tsx` resolves a bundled SVG per vendor and falls back to a drawn monogram; nothing
 * is fetched, from anywhere. `vendor-name.tsx` supplies the spelling a person would write, and the
 * id stays on the card underneath it because the id is what the graph, every payload and every URL
 * key on.
 *
 * ## The tier badge is monochrome on purpose
 *
 * Colour on this console carries a change kind, a rung, or a run outcome, and a tier is none of
 * the three: `coded` is not better than `generated`, and a palette across the four would read as a
 * quality ordering that nothing measured. The vocabulary is the registry's — `sync/signals/
 * registry.py` emits `coded`, `generated` and `mcp`, and `sync/dashboard/adapters.py` adds
 * `unregistered` for history keyed by a vendor id nothing serves any more. A screen inventing a
 * fifth tier is the same defect as a screen inventing a number.
 *
 * ## Three nothings, and the card says which
 *
 * The catalogue not answering, the inventory holding no row for this vendor, and an adapter that
 * has never delivered are three different facts and each has its own sentence. The share bar
 * beneath the figure is a ratio of two measured counts with its denominator on the line above it,
 * never a percentage and never a grade.
 *
 * ## What the card does not carry, and why the omission is a measurement
 *
 * **Products named.** The count is `1` for twenty-seven of the thirty integrations in the corpus,
 * because only a vendor adapter can group operations onto a product and almost none does. A column
 * that reads `1` on every card is furniture pretending to be data — the same argument that kept the
 * rung chip off the overview map. The drawer names the products instead, which is the useful form
 * of the same fact and the one that cannot be a constant.
 *
 * **There is no freshness verdict, because nothing measures freshness.** `last_change_at` is the
 * newest row the graph holds, not the last time the adapter was asked — nothing records an intake
 * attempt, only its result. The card names the timestamp for what it is; the inspector carries the
 * qualification and the intake record itself.
 */

import type { ReactNode } from "react"

import { FactList, type Fact } from "@/components/fact-list"
import { RungBadge } from "@/components/provenance"
import { RelativeTime } from "@/components/relative-time"
import { Absent, Formatted } from "@/components/status"
import { Tag } from "@/components/tag"
import type { AdapterRow } from "@/api/types"
import { NEVER_DELIVERED_NOTE } from "@/features/settings/adapter-table"
import type { DeckRow } from "@/features/vendors/vendor-deck"
import { VendorMark } from "@/features/vendors/vendor-mark"
import { orAbsent } from "@/lib/format"

/**
 * Every tier `GET /api/adapters` can carry, in the order the registry builds them.
 *
 * Exported so a test can prove the set has not drifted from the registry, and so anything that
 * ever ranges over tiers takes the payload's vocabulary rather than writing its own.
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

/** A vendor the index bound and the adapter inventory does not name. Not the same as never delivering. */
export const NO_ADAPTER_ROW_NOTE = "the adapter inventory carries no row for this vendor"

/** The catalogue errored: nothing was measured about this vendor's adapter, which is a different
 *  fact from measuring that it has none. */
export const CATALOGUE_UNANSWERED_NOTE = "the adapter catalogue did not answer"

/** Why a coded adapter has no source, said as the fact it is rather than as an absence. */
export const CODED_SOURCE_NOTE = "written in this repository"

/** The coverage answer holds a call-site count for this vendor and no operation row under it. */
export const NO_OPERATIONS_NOTE = "the coverage answer named no operation"

/** What the timestamp beside it does and does not mean. Never shortened into a label. */
export const FRESHNESS_QUALIFICATION =
  "The newest change the graph holds, not the last time the adapter was asked — nothing records " +
  "an intake attempt, only its result."

/** Where an adapter's specification is read from, or the fact that there is no repository behind it. */
export function servedFrom(adapter: AdapterRow): ReactNode {
  if (adapter.kind === "coded" && adapter.source === null) return CODED_SOURCE_NOTE
  return (
    <span className="font-mono text-meta">
      <Formatted value={orAbsent(adapter.source)} />
    </span>
  )
}

function AbsentMeta({ children }: { children: string }) {
  return (
    <span className="text-meta">
      <Absent>
        <span>{children}</span>
      </Absent>
    </span>
  )
}

/**
 * What the graph holds against this integration, in one cell.
 *
 * Two answers here and they are two different facts: the adapter has never delivered, or it has
 * delivered *n* rows. `0` is reachable and is a number — Sync read the specification and had
 * nothing to say — so the first may never render as one.
 *
 * The other two nothings (the catalogue never answered, the inventory named no adapter) are said
 * once, in the header, and this row is not drawn at all under either. It used to be, and the same
 * sentence appeared twice on one card — which reads as two separate facts about two different
 * things and is exactly the noise the owner named as *"too much information"*.
 */
function ChangesRecorded({ adapter }: { adapter: AdapterRow }) {
  if (adapter.changes === null) return <AbsentMeta>{NEVER_DELIVERED_NOTE}</AbsentMeta>
  return <span className="font-mono tabular-nums">{adapter.changes.toLocaleString()}</span>
}

export interface VendorCardProps {
  /** Everything derived about this integration. `vendor-deck.ts` builds it and holds the nulls. */
  row: DeckRow
  /** `false` when the catalogue query failed — absence of an answer, not an answer of none. */
  catalogueAnswered: boolean
  /**
   * Call sites the index bound in this repository, across every integration.
   *
   * The denominator of the share bar, and it is on screen beside the figure rather than folded
   * into a percentage: `web/CLAUDE.md` refuses a rate without its denominator, and a bar is a
   * rate drawn.
   */
  totalCallSites: number
  /** Whether this card is the one open in the inspector. */
  selected: boolean
  onSelect: () => void
}

export function VendorCard({
  row,
  catalogueAnswered,
  totalCallSites,
  selected,
  onSelect,
}: VendorCardProps) {
  const facts: Fact[] = [
    {
      label: "Operations reached",
      value:
        row.operations === null ? (
          <AbsentMeta>{NO_OPERATIONS_NOTE}</AbsentMeta>
        ) : (
          <span className="font-mono tabular-nums">{row.operations.toLocaleString()}</span>
        ),
    },
    ...(catalogueAnswered && row.adapter !== null
      ? [
          {
            label: "Vendor changes recorded",
            value: <ChangesRecorded adapter={row.adapter} />,
          },
        ]
      : []),
    {
      label: "Last indexed",
      value: (
        <span className="font-mono text-meta">
          <RelativeTime iso={row.lastIndexed} />
        </span>
      ),
    },
  ]

  // Clamped rather than trusted: the two counts come from one read, but a bar wider than its track
  // would silently overflow the card rather than fail somewhere a test can see it.
  const share =
    totalCallSites > 0 ? Math.min(100, (row.callSites / totalCallSites) * 100) : 0

  return (
    // The whole card is the control, and the control is one overlaid button rather than a `<button>`
    // wrapped around the content. A button may only contain phrasing content, so wrapping would put
    // the heading and the fact list inside it — and it would fold thirty cards' worth of text into
    // thirty accessible names. The overlay keeps `<h3>` a heading and gives the control one short
    // name of its own.
    <article
      data-testid="vendor-card"
      data-state={selected ? "selected" : undefined}
      // `transition-colors` only: a card that grew or lifted under the pointer would be a geometry
      // change, which `tests/test_console_design_tokens.py` refuses outside direct manipulation.
      className="relative flex min-w-0 flex-1 flex-col gap-row rounded-surface border border-line bg-surface p-section transition-colors hover:bg-surface-emphasis focus-within:ring-1 focus-within:ring-ring data-[state=selected]:border-primary data-[state=selected]:bg-surface-emphasis"
    >
      <button
        type="button"
        onClick={onSelect}
        aria-pressed={selected}
        aria-label={`${row.name} — what this codebase records`}
        className="absolute inset-0 z-10 rounded-surface focus:outline-none"
      />

      <header className="flex min-w-0 items-start gap-row">
        <VendorMark vendorId={row.vendorId} />
        <span className="flex min-w-0 flex-1 flex-col">
          <h3 className="min-w-0 truncate text-emphasis">{row.name}</h3>
          <span className="min-w-0 truncate font-mono text-meta text-ink-muted">{row.vendorId}</span>
        </span>
        {!catalogueAnswered ? (
          <AbsentMeta>{CATALOGUE_UNANSWERED_NOTE}</AbsentMeta>
        ) : row.adapter === null ? (
          <AbsentMeta>{NO_ADAPTER_ROW_NOTE}</AbsentMeta>
        ) : (
          <Tag>{adapterTierLabel(row.adapter.kind)}</Tag>
        )}
      </header>

      <div className="flex min-w-0 flex-col gap-field">
        <div className="flex min-w-0 flex-wrap items-baseline gap-row">
          <span className="text-figure tabular-nums text-ink">{row.callSites.toLocaleString()}</span>
          <span className="text-meta text-ink-muted">
            of {totalCallSites.toLocaleString()} call sites indexed here
          </span>
          {/* The rung qualifies the figure it sits beside: this is what the static index found,
              never what traffic showed. Monochrome by `console-surface.md` — evidence class is
              not a state and never wears the status ramp. */}
          <RungBadge rung="static" />
        </div>
        {/* Decorative: both numbers are on the line above, so a reader the bar does not reach has
            lost nothing. It exists so thirty cards can be ranked at a glance without reading. */}
        <div aria-hidden="true" className="h-1 w-full overflow-hidden rounded-control bg-surface-subtle">
          <div className="h-full rounded-control bg-line-strong" style={{ width: `${share}%` }} />
        </div>
      </div>

      <FactList facts={facts} />
    </article>
  )
}
