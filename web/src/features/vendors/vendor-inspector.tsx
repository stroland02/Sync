/**
 * The drawer behind one card: everything recorded about one integration that will not fit on it.
 *
 * **It issues no request.** Every fact here is already in the two answers the deck was built from
 * — `GET /api/repositories/{repo}/coverage` and `GET /api/adapters` — so opening a card costs
 * nothing and closing it loses nothing. That is also why it is a drawer rather than a docked
 * column: owner ruling, a detail must never squeeze the list it came from.
 *
 * ## What it deliberately does not restate
 *
 * The vendor's own record already has a screen. `vendor-page.tsx` carries the exposure table (every
 * operation, its rung, whether traffic confirmed it), the changes feed, the findings open against
 * it and the source list. None of that is redrawn here — this drawer holds the three things that
 * are *not* on any vendor-scoped screen today:
 *
 * - **The products this repository calls**, from the coverage answer's own grouping. The Services
 *   screen lists products across every vendor; nowhere lists one vendor's under its own name.
 * - **Where the record comes from** — `AdapterRow.sources`, the feeds the graph's rows arrived on.
 * - **The last intake attempt.** `last_attempt_at` / `_outcome` / `_reason` answer the question
 *   `last_change_at` cannot: whether anybody has *asked* recently. A quiet healthy adapter and an
 *   adapter nobody runs are indistinguishable without it, and today it is only on the Settings
 *   inventory, at deployment scope.
 *
 * Findings stay off this screen entirely (owner ruling, 2026-08-19): a finding is an Errors &
 * Incidents fact and Findings is where it is answered.
 *
 * ## The nulls
 *
 * A `null` intake record is not "never asked" — the attempt table began when it began, so it means
 * this console holds no record of an attempt. That is a limit of the record, not a fact about the
 * adapter, and the sentence says so.
 */

import type { ReactNode } from "react"
import { Link } from "react-router"

import { FactList, type Fact } from "@/components/fact-list"
import { InfoHint } from "@/components/info-hint"
import { RelativeTime } from "@/components/relative-time"
import { Absent } from "@/components/status"
import { Tag } from "@/components/tag"
import {
  CATALOGUE_UNANSWERED_NOTE,
  FRESHNESS_QUALIFICATION,
  NO_ADAPTER_ROW_NOTE,
  NO_OPERATIONS_NOTE,
  adapterTierLabel,
  servedFrom,
} from "@/features/vendors/vendor-card"
import type { DeckRow } from "@/features/vendors/vendor-deck"
import { NEVER_DELIVERED_NOTE } from "@/features/settings/adapter-table"
import { callSitesHref, vendorHref } from "@/lib/hrefs"

/** Nothing has mapped this vendor's operations onto a product. Work not done, never a count of none. */
export const NO_PRODUCTS_NOTE = "not grouped into products yet"

/** No attempt row exists for this vendor. The record's limit, never a claim about the adapter. */
export const NO_INTAKE_RECORD_NOTE =
  "no intake attempt is recorded here — the attempt record began when the table did, which is not the same as nobody having asked"

/** The static index is what bound these call sites. Said once here, in full. */
export const STATIC_SCOPE_NOTE =
  "Counted over what the static index found in this repository. Traffic is reported on Signals, beside this and never blended into it."

function Section({ heading, children }: { heading: string; children: ReactNode }) {
  return (
    <section className="flex min-w-0 flex-col gap-row">
      <h3 className="text-section">{heading}</h3>
      {children}
    </section>
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

export interface VendorInspectorProps {
  row: DeckRow
  /** The scope every link carries. A vendor's record is reachable fleet-wide and inside a repository. */
  repoId: string
  /** `false` when the catalogue query failed — nothing was read, which is not an answer of none. */
  catalogueAnswered: boolean
  /** Distinct products named across the whole coverage answer, so one vendor's share has a scale. */
  products: readonly string[]
}

export function VendorInspector({ row, repoId, catalogueAnswered, products }: VendorInspectorProps) {
  const calls: Fact[] = [
    {
      label: "Call sites bound",
      value: <span className="font-mono tabular-nums">{row.callSites.toLocaleString()}</span>,
    },
    {
      label: "Operations reached",
      value:
        row.operations === null ? (
          <AbsentMeta>{NO_OPERATIONS_NOTE}</AbsentMeta>
        ) : (
          <span className="font-mono tabular-nums">{row.operations.toLocaleString()}</span>
        ),
    },
    {
      label: "Last indexed",
      value: (
        <span className="font-mono text-meta">
          <RelativeTime iso={row.lastIndexed} />
        </span>
      ),
    },
  ]

  return (
    <div className="flex min-w-0 flex-col gap-8">
      <Section heading="What this codebase calls">
        <FactList facts={calls} />
        <p className="max-w-prose text-meta text-ink-muted">{STATIC_SCOPE_NOTE}</p>
        <div className="flex min-w-0 flex-col gap-field">
          <span className="furniture text-meta text-ink-muted">Products named</span>
          {products.length === 0 ? (
            <AbsentMeta>{NO_PRODUCTS_NOTE}</AbsentMeta>
          ) : (
            <div className="flex min-w-0 flex-wrap gap-field">
              {products.map((product) => (
                <Tag key={product}>{product}</Tag>
              ))}
            </div>
          )}
        </div>
      </Section>

      <Section heading="What the integration has published">
        {!catalogueAnswered ? (
          <AbsentMeta>{CATALOGUE_UNANSWERED_NOTE}</AbsentMeta>
        ) : row.adapter === null ? (
          <AbsentMeta>{NO_ADAPTER_ROW_NOTE}</AbsentMeta>
        ) : (
          <>
            <FactList
              facts={[
                { label: "Adapter tier", value: <Tag>{adapterTierLabel(row.adapter.kind)}</Tag> },
                { label: "Served from", value: servedFrom(row.adapter) },
                ...(row.adapter.changes === null
                  ? [{ label: "Adapter intake", value: <AbsentMeta>{NEVER_DELIVERED_NOTE}</AbsentMeta> }]
                  : [
                      {
                        label: "Changes recorded",
                        value: (
                          <span className="font-mono tabular-nums">
                            {row.adapter.changes.toLocaleString()}
                          </span>
                        ),
                      },
                      {
                        label: "Operations named",
                        // Never `?? 0`: `changes` and `operations` go null together, but a fallback
                        // here would print a measured nought for a read that returned nothing the
                        // day that stops being true.
                        value:
                          row.adapter.operations === null ? (
                            <AbsentMeta>{NEVER_DELIVERED_NOTE}</AbsentMeta>
                          ) : (
                            <span className="font-mono tabular-nums">
                              {row.adapter.operations.toLocaleString()}
                            </span>
                          ),
                      },
                      {
                        label: "Newest change recorded",
                        value: (
                          <span className="font-mono text-meta">
                            <RelativeTime iso={row.adapter.last_change_at} />
                          </span>
                        ),
                      },
                    ]),
              ]}
            />
            {row.adapter.changes !== null && (
              <p className="max-w-prose text-meta text-ink-muted">{FRESHNESS_QUALIFICATION}</p>
            )}
            <div className="flex min-w-0 flex-col gap-field">
              <span className="furniture text-meta text-ink-muted">Feeds the rows arrived on</span>
              {row.adapter.sources === null || row.adapter.sources.length === 0 ? (
                <AbsentMeta>{NEVER_DELIVERED_NOTE}</AbsentMeta>
              ) : (
                <div className="flex min-w-0 flex-wrap gap-field">
                  {row.adapter.sources.map((source) => (
                    <Tag key={source}>{source}</Tag>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </Section>

      {catalogueAnswered && row.adapter !== null && (
        <Section heading="Last intake attempt">
          {row.adapter.last_attempt_at === null ? (
            <AbsentMeta>{NO_INTAKE_RECORD_NOTE}</AbsentMeta>
          ) : (
            <FactList
              facts={[
                {
                  label: "Asked",
                  value: (
                    <span className="font-mono text-meta">
                      <RelativeTime iso={row.adapter.last_attempt_at} />
                    </span>
                  ),
                },
                {
                  label: "Outcome",
                  value:
                    row.adapter.last_attempt_outcome === null ? (
                      <AbsentMeta>no outcome is recorded against that attempt</AbsentMeta>
                    ) : (
                      <Tag>{row.adapter.last_attempt_outcome}</Tag>
                    ),
                },
                {
                  label: "Reason",
                  value:
                    row.adapter.last_attempt_reason === null ? (
                      <AbsentMeta>none — a successful attempt records no reason</AbsentMeta>
                    ) : (
                      <Tag>{row.adapter.last_attempt_reason}</Tag>
                    ),
                },
              ]}
            />
          )}
        </Section>
      )}

      <Section heading="Go on">
        <nav className="flex min-w-0 flex-col gap-row" aria-label={`More about ${row.name}`}>
          <Link
            className="text-body text-brand-link underline underline-offset-2"
            to={vendorHref(repoId, row.vendorId)}
          >
            Open the full record for {row.name} →
          </Link>
          <Link
            className="text-body text-brand-link underline underline-offset-2"
            to={`${callSitesHref(repoId)}?call_sites_vendor=${encodeURIComponent(row.vendorId)}`}
          >
            Browse the {row.callSites.toLocaleString()} call sites that bind it →
          </Link>
          <p className="max-w-prose text-meta text-ink-muted">
            The full record carries what this drawer does not: every operation with its rung and
            whether traffic confirmed it, the changes feed, and the findings open against it.
            <InfoHint label="About what is on the record screen">
              This drawer is built from the two answers the deck already holds, so it costs no
              request. The record screen fetches the vendor&rsquo;s own payloads, which are scoped
              to the vendor rather than to this repository — the drawer says so on every figure it
              draws.
            </InfoHint>
          </p>
        </nav>
      </Section>
    </div>
  )
}
