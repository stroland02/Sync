/**
 * One API service: the calls this codebase makes on it, then everything else in tabs.
 *
 * **The owner's second re-ruling of 2026-08-19, superseding both prior orders.** Decision 29 led
 * with exposure; the morning's re-ruling led with the changes feed. Looking at both, the owner's
 * settled shape is neither stack: the API-calls table is the page's fixed answer — the organized
 * call patterns and operations for this one vendor — and the other three tables (what the vendor
 * published, the findings open against it, where its spec is read from) spread into tabs beneath
 * it rather than stacking into a scroll.
 *
 * The tab is a query parameter, not component state: a shared address opens on the tab the
 * sender was reading. Only the active table mounts — three data-fetching tables mounted to show
 * one is the cost `page-tabs.tsx` documents against the vendored `Tabs`.
 */

import { useParams } from "react-router"

import { FactList } from "@/components/fact-list"
import { VendorChangesCard } from "@/features/vendors/vendor-changes-table"
import { VendorExposureCard } from "@/features/vendors/vendor-exposure-card"
import {
  VendorFindingsCard,
  VendorFindingsControls,
} from "@/features/vendors/vendor-findings-table"
import { VendorSourcesCard } from "@/features/vendors/vendor-sources-card"
import { DetailGrid } from "@/layouts/detail-grid"
import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"
import { UnknownRoute } from "@/layouts/unknown-route"
import { chipSurface } from "@/lib/selectable-surface"
import { useFilterParam } from "@/lib/use-filter-param"

export interface VendorPageProps {
  readonly question?: string
}

const PANELS = [
  { id: "changes", label: "Changes" },
  { id: "findings", label: "Findings" },
  { id: "sources", label: "Sources" },
] as const

type PanelId = (typeof PANELS)[number]["id"]

export function VendorPage() {
  // **The route is the scope**, and it used to be a query string: this read
  // `searchParams.get("repo_id")` while the route carries `:repoId`, so an address naming a
  // workspace could still render a fleet-wide claim -- the screen contradicting its own URL.
  const { vendorId, repoId } = useParams<{ vendorId: string; repoId: string }>()
  const [panelParam, setPanel] = useFilterParam("panel")
  if (vendorId === undefined || repoId === undefined) return <UnknownRoute />

  // An unknown value falls back rather than rendering nothing: a mistyped shared address should
  // land on the default tab, not on a page with a strip and no table.
  const panel: PanelId = PANELS.some((entry) => entry.id === panelParam)
    ? (panelParam as PanelId)
    : "changes"

  // The panel chips are what narrow this screen, so they are the controls band rather than a
  // strip inside the content -- which is what `ScreenFrame` exists to keep in one place across
  // every screen.
  const controls = (
    <nav aria-label="Vendor records" className="flex flex-wrap items-center gap-row">
      {PANELS.map((entry) => (
        <button
          key={entry.id}
          type="button"
          aria-pressed={entry.id === panel}
          onClick={() => setPanel(entry.id === "changes" ? null : entry.id)}
          className={`rounded-control border px-row py-field text-body ${chipSurface(entry.id === panel)}`}
        >
          {entry.label}
        </button>
      ))}
    </nav>
  )

  // Which record is mounted, not how many rows it holds: the counts belong to the cards, which
  // each fetch their own and publish nothing here. A `listing` says what is on screen without
  // claiming a number this component has not got.
  const status: StatusSegment[] = [
    { kind: "listing", label: "Showing", text: PANELS.find((e) => e.id === panel)!.label },
    { kind: "note", text: `for ${vendorId} in ${repoId}` },
  ]

  return (
    <ScreenFrame status={status} controls={controls}>
      <section className="flex flex-col gap-8">
      {/* Header and Fact List */}
      <DetailGrid
        railSide="end"
        rail={
          <FactList
            facts={[
              { label: "Vendor", value: <span className="font-mono">{vendorId}</span> },
              {
                // One scope fact, not two: "Repository scope" and "Findings counted over"
                // carried the same value under different labels, which reads as two facts.
                label: "Findings counted over",
                value: <span className="font-mono">{repoId}</span>,
              },
              {
                label: "Changes counted over",
                value: "The vendor, never a repository",
              },
            ]}
          />
        }
      >
        <div className="flex min-w-0 flex-col gap-section">
          <p className="max-w-prose text-body text-muted-foreground">
            Every operation <span className="font-mono">{repoId}</span> calls on {vendorId}, then
            the vendor&rsquo;s own record in the tabs beneath: what it published, what is open
            against it here, and where its spec is read from.
          </p>
        </div>
      </DetailGrid>

      <div data-testid="vendor-exposure">
        <VendorExposureCard vendorId={vendorId} repoId={repoId} />
      </div>

      <div className="flex flex-col gap-8" data-testid="vendor-panels">
        {panel === "changes" && <VendorChangesCard vendorId={vendorId} repoId={repoId} />}
        {panel === "findings" && (
          <>
            <VendorFindingsControls vendorId={vendorId} repoId={repoId} />
            <VendorFindingsCard vendorId={vendorId} repoId={repoId} />
          </>
        )}
        {panel === "sources" && <VendorSourcesCard vendorId={vendorId} repoId={repoId} />}
      </div>
      </section>
    </ScreenFrame>
  )
}
