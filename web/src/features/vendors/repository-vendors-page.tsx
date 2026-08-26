/**
 * The integrations one repository calls — a locked deck of cards, and nothing else.
 *
 * ## What changed, and why "cards only" was structural rather than cosmetic
 *
 * **Owner ruling, 2026-08-26: *"Vendors should fully switch to cards."*** This screen was a hybrid.
 * It carried a `VendorCard` grid *and* a four-column table of the same rows behind a `viewMode`
 * constant that could only ever be `"cards"` — eighteen table references and a dead `TierFilter`,
 * all of it reachable by one edit. Both are gone. The screen is now `ScreenFrame layout="locked"`:
 * it owns every scrollbar on the page, the deck scrolls inside its pane, and the pane's header and
 * footer stay put over it.
 *
 * The table's four columns did not evaporate — each became a fact on the card that replaced it, and
 * two more joined them (operations reached, products named) that the table had no room for. A card
 * is a bigger object than a row, so a screen that swaps one for the other and shows *less* has
 * merely made the same table taller.
 *
 * ## Which nothing it is, four times, and none of them is a zero
 *
 * The catalogue not answering, the inventory naming no adapter, an adapter that has never
 * delivered, and a coverage answer that grouped nothing into products are four different facts. The
 * card carries a sentence for each. **A vendor with nothing measured never gets a card that looks
 * like a measured zero** — that is the ruling this screen is easiest to break, because every one of
 * those sentences is one `?? 0` away from becoming a nought.
 *
 * ## The scope check is still the load-bearing part
 *
 * `/api/repositories/{id}/coverage` echoes the `repo_id` it was computed for. A caller that ignores
 * it renders the fleet's integrations under one repository's name, and this console has shipped
 * that defect before — `codebases-panel.tsx` printed the fleet-wide `total_findings` under every
 * card until `M14-W265`. So the deck draws only when the answer's own scope matches the address,
 * and says plainly when it does not.
 *
 * ## What this screen deliberately does not show
 *
 * The owner also asked for each vendor's *"api formats rules calls limits structures and data
 * traces"*. Rate limits, auth rules and call structures are captured by no stage — they are in no
 * table and no payload — so the screen names that as absent work rather than drawing empty panels.
 * Findings stay on Findings (owner ruling, 2026-08-19): a finding is an Errors & Incidents fact.
 *
 * **"Add a vendor" stays, by name, on every branch**, because *how do I add one?* is asked most
 * often on a screen that came back empty or unanswered. It is a drawer of text rather than a form:
 * the API is read-only, and a vendor becomes watched when this codebase calls it and an index pass
 * finds the call site — not by being added to a list.
 */

import { Boxes, Search, X } from "lucide-react"
import { useMemo, useState } from "react"
import { useParams } from "react-router"

import { useAdapters, useRepositoryCoverage } from "@/api/queries"
import { DetailLayout, useSelectionKeys, useSelectionParam } from "@/components/detail-layout"
import { InfoHint } from "@/components/info-hint"
import { PanelPane } from "@/components/pane"
import { RelativeTime } from "@/components/relative-time"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group"
import { AddVendorDrawer } from "@/features/vendors/add-vendor-drawer"
import { IntegrationsKpis } from "@/features/vendors/integrations-kpis"
import { VendorCard } from "@/features/vendors/vendor-card"
import {
  deckRows,
  matchesSearch,
  newestIndexed,
  productsFor,
  type DeckRow,
} from "@/features/vendors/vendor-deck"
import { VendorInspector } from "@/features/vendors/vendor-inspector"
import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"
import { UnknownRoute } from "@/layouts/unknown-route"

export interface RepositoryVendorsPageProps {
  readonly question?: string
}

/** The scope note that survives from the retired table's caption. Never shortened into a label. */
const SURFACE_NOTE =
  "This deck is what INDEX bound in this repository. A vendor's published rate limits, auth rules " +
  "and call structures are not shown, because no stage captures them yet — that is work not done " +
  "rather than a vendor with none."

/** What a card that is not in the narrowed deck says, rather than an empty drawer. */
export const SELECTION_OFF_DECK_NOTE =
  "The selected integration is not in the narrowed deck. Clear the search to bring it back."

/**
 * The search box, filtering a list already in hand.
 *
 * **Live rather than on submit, and local rather than in the URL**, which is the opposite of
 * `PrefixFilter` on the tables — deliberately, and for the reason that rule was written. A table
 * filter is a request, so a debounce is a guess and an explicit submit is one request for one
 * intention. This narrows thirty objects already rendered: there is nothing to debounce and nothing
 * to reset. And it stays out of the URL because a history entry per keystroke would make Back
 * unusable on the one screen whose Back is already spent closing the drawer.
 */
function DeckSearch({ value, onChange }: { value: string; onChange: (next: string) => void }) {
  return (
    <InputGroup className="max-w-[20rem]">
      <InputGroupAddon align="inline-start">
        <Search aria-hidden="true" className="size-4 text-ink-muted" />
      </InputGroupAddon>
      <InputGroupInput
        aria-label="Search the integrations on this deck"
        placeholder="Search integrations"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
      {value !== "" && (
        <InputGroupAddon align="inline-end">
          <InputGroupButton type="button" aria-label="Clear the search" onClick={() => onChange("")}>
            <X aria-hidden="true" className="size-3" />
          </InputGroupButton>
        </InputGroupAddon>
      )}
    </InputGroup>
  )
}

export function RepositoryVendorsPage() {
  const { repoId } = useParams<{ repoId: string }>()
  const scope = repoId ?? ""
  const adaptersQuery = useAdapters()
  const coverage = useRepositoryCoverage(scope)
  const [search, setSearch] = useState("")
  const [openVendor, setOpenVendor] = useSelectionParam("vendors_open")

  // The answer names the scope it was computed for, and a mismatch is refused rather than shown
  // with a caveat: a fleet-wide list under one repository's heading is a claim about that
  // repository which nothing computed.
  const answer = coverage.data
  const inScope = answer !== undefined && answer.repo_id === scope

  const adapters = adaptersQuery.isSuccess ? adaptersQuery.data.adapters : null
  const rows = useMemo<DeckRow[]>(
    () => (answer !== undefined && answer.repo_id === scope ? deckRows(answer, adapters) : []),
    [answer, adapters, scope],
  )
  const shown = useMemo(() => rows.filter((row) => matchesSearch(row, search)), [rows, search])
  const ids = useMemo(() => shown.map((row) => row.vendorId), [shown])
  useSelectionKeys(ids, openVendor, setOpenVendor)

  const selected = openVendor === null ? null : (shown.find((row) => row.vendorId === openVendor) ?? null)

  // On every branch below, including the two failures: the drawer reads the catalogue, which is a
  // different question from the coverage read that failed here, so it still has an answer.
  const controls =
    repoId === undefined ? undefined : (
      <>
        <DeckSearch value={search} onChange={setSearch} />
        <AddVendorDrawer repoId={repoId} />
      </>
    )

  if (repoId === undefined) return <UnknownRoute />

  if (coverage.isPending) {
    return (
      <ScreenFrame
        controls={controls}
        status={[{ kind: "none", why: "asking which integrations this repository calls" }]}
      >
        <LoadingState what="the integrations this repository calls" />
      </ScreenFrame>
    )
  }

  if (coverage.isError) {
    return (
      <ScreenFrame
        controls={controls}
        status={[{ kind: "none", why: "the index coverage did not answer" }]}
      >
        <ErrorState
          error={coverage.error}
          what="the integrations this repository calls"
          onRetry={() => void coverage.refetch()}
        />
      </ScreenFrame>
    )
  }

  if (!inScope) {
    return (
      <ScreenFrame
        controls={controls}
        status={[{ kind: "none", why: "the index coverage answered for another repository" }]}
      >
        <IntegrationsKpis repoId={repoId} />
        <EmptyState
          headline="This answer was computed for a different scope."
          detail={
            `The index coverage that arrived names its scope as ` +
            `${answer?.repo_id ?? "another repository"}, not ${repoId}. Its integrations are not ` +
            `shown here, because a fleet-wide list under one repository's name is a claim about ` +
            `that repository which nothing computed.`
          }
        />
      </ScreenFrame>
    )
  }

  if (rows.length === 0) {
    return (
      <ScreenFrame
        controls={controls}
        status={[
          { kind: "listing", label: "Integrations", text: "none bound here" },
          { kind: "note", text: SURFACE_NOTE },
        ]}
      >
        <IntegrationsKpis repoId={repoId} />
        <EmptyState
          headline="No integration is bound to this repository."
          detail="One appears here once INDEX finds a call site binding this repository to it."
          command={`uv run sync index --repo ${repoId}`}
        />
      </ScreenFrame>
    )
  }

  const narrowed = search.trim() !== ""
  const status: StatusSegment[] = [
    {
      kind: "listing",
      label: "Integrations",
      text: narrowed
        ? `${shown.length.toLocaleString()} of ${rows.length.toLocaleString()} bound here`
        : `${rows.length.toLocaleString()} bound here`,
    },
    {
      kind: "figure",
      label: "Call sites indexed",
      value: answer.total_call_sites.toLocaleString(),
      scope: "static evidence — what the last index pass found in this repository",
    },
    { kind: "note", text: SURFACE_NOTE },
  ]

  return (
    <ScreenFrame
      controls={controls}
      status={status}
      layout="locked"
      subtitle="Every integration this codebase calls, as the last index pass found it."
    >
      <section className="flex min-h-0 min-w-0 flex-1 flex-col gap-8">
        {/* Portals into the chrome's second row; it draws nothing here unless its own read is in
            flight or failed, which is a fact about this screen and belongs on it. */}
        <IntegrationsKpis repoId={repoId} />

        <PanelPane
          label="Integrations bound in this codebase"
          icon={Boxes}
          hint={
            <InfoHint label="About this deck">
              One card per integration the static index found a call site for, busiest first. The
              figure on each card is statically indexed call sites — not calls and not traffic,
              which is what the rung beside it says. An integration Sync knows about and this
              codebase does not call is not here; &ldquo;Add a vendor&rdquo; lists those.
            </InfoHint>
          }
          // The deck's scroll belongs to `DetailLayout`'s list column, which already applies it —
          // a second scroller around it would be two scrollbars over one body.
          scroll={false}
          footer={
            <>
              <span className="furniture shrink-0">Newest call site indexed</span>
              <span className="shrink-0 font-mono">
                <RelativeTime iso={newestIndexed(rows)} />
              </span>
              <span className="min-w-0 truncate">
                — staleness, not a promise the index is current
              </span>
            </>
          }
        >
          <DetailLayout
            docked
            title={selected === null ? "Integration" : selected.name}
            subtitle={selected === null ? undefined : selected.vendorId}
            onClose={() => setOpenVendor(null)}
            detail={
              openVendor === null ? null : selected === null ? (
                <p className="max-w-prose text-body text-ink-muted">{SELECTION_OFF_DECK_NOTE}</p>
              ) : (
                <VendorInspector
                  row={selected}
                  repoId={repoId}
                  catalogueAnswered={adaptersQuery.isSuccess}
                  products={productsFor(answer, selected.vendorId)}
                />
              )
            }
            list={
              shown.length === 0 ? (
                <div className="p-section">
                  <EmptyState
                    headline="No integration on this deck matches the search."
                    detail={`Nothing bound in ${repoId} is named like “${search.trim()}”. The deck holds ${rows.length.toLocaleString()} integrations.`}
                  />
                </div>
              ) : (
                <ul className="grid min-w-0 grid-cols-1 gap-section p-section md:grid-cols-2 2xl:grid-cols-3">
                  {shown.map((row) => (
                    <li key={row.vendorId} className="flex min-w-0">
                      <VendorCard
                        row={row}
                        catalogueAnswered={adaptersQuery.isSuccess}
                        totalCallSites={answer.total_call_sites}
                        selected={row.vendorId === openVendor}
                        onSelect={() =>
                          setOpenVendor(row.vendorId === openVendor ? null : row.vendorId)
                        }
                      />
                    </li>
                  ))}
                </ul>
              )
            }
          />
        </PanelPane>
      </section>
    </ScreenFrame>
  )
}
