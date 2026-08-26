/**
 * The catalogue of what Sync looks for: every detector, what it matched, and what its claims rest
 * on.
 *
 * **Rebuilt 2026-08-26 as a locked four-pane bento**, against
 * `docs/stitch_sync_developer_console/.../api_documentation/` — the reference's index rail, wide
 * reading pane and right-hand evidence rail, which is the arrangement a catalogue with per-item
 * evidence wants. What it replaced was one unbounded scrolling column: an automation table, a rung
 * panel, then a card per detector, each card carrying three tallies, so twelve detectors meant
 * thirty-six tables stacked down a page nobody could hold in view.
 *
 * **The three nothings this screen has to keep apart**, and none of them is a zero:
 *
 * - **Never indexed.** A detector fires against a corpus, and a repository nothing has ever read
 *   has no corpus. `catalogueState` joins the roll-up to the Overview's own index answer, because
 *   `GET /api/detectors` returns the same empty list for this as for a counted zero.
 * - **Counted zero.** The corpus was read and no open finding here is attributed to any detector.
 * - **Never fired.** A detector appears here only once it has raised an open finding; the graph
 *   keeps no registry of which detectors exist. So a detector raising nothing is *absent*, and that
 *   absence is indistinguishable from a detector that was never installed. Said in the catalogue's
 *   own footer, on every branch, because the empty screen is where it bites hardest.
 *
 * **No precision, accuracy or ranking figure.** Detectors are not competing — more findings is
 * neither better nor worse than fewer — and a ratio computed from open findings alone, with no
 * labelled corpus behind it, would measure nothing. The order is the payload's own, alphabetical,
 * and nothing re-sorts by count.
 *
 * The automatic lane keeps its pane by the owner's ruling of 2026-08-19: this page is where a
 * reader sees what the platform did *without* a human.
 */

import { Layers, Radar, ScanSearch, X } from "lucide-react"
import { useMemo } from "react"
import { useParams } from "react-router"

import { useDetectors, useOverview } from "@/api/queries"
import type { DetectorRow } from "@/api/types"
import { useSelectionKeys, useSelectionParam } from "@/components/detail-layout"
import { InfoHint } from "@/components/info-hint"
import { KpiStrip } from "@/components/kpi-strip"
import { PanelPane } from "@/components/pane"
import { ScopeChip } from "@/components/scope-chip"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { Absent } from "@/components/status"
import { AutomationPanel } from "@/features/tickets/automation-panel"
import { Pending } from "@/features/findings/pending"
import {
  catalogueState,
  claimKinds,
  rungLadder,
  selectDetector,
  type CorpusAnswer,
} from "@/features/detectors/detector-catalogue"
import { DetectorEvidence, EveryDetector } from "@/features/detectors/detector-evidence"
import { DetectorIndex } from "@/features/detectors/detector-index"
import { RungLadder } from "@/features/detectors/rung-ladder"
import { Pane, PaneScroll } from "@/layouts/pane"
import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"
import { UnknownRoute } from "@/layouts/unknown-route"
import { formatTimestamp } from "@/lib/format"

export interface DetectorsPageProps {
  readonly question?: string
}

const QUESTION = "Every detector that has raised a finding here, and the evidence behind its claims."

/** One frozen empty list, so a pending read does not hand every memo below a new array. */
const NO_ROWS: readonly DetectorRow[] = []

/** Open findings only, everywhere on this screen. Said once, in the band, rather than per panel. */
const OPEN_ONLY =
  "Open findings only. A closed finding is invisible to this roll-up, as it is everywhere else in " +
  "the console — that is the read the graph offers, not a filter this screen applied."

/**
 * The catalogue's own qualification, pinned under the rows rather than inside the scroll.
 *
 * Both sentences were rendered elsewhere before this rebuild — the first at the top of the page,
 * two panels above the rows it is about, and the second once inside every card, which is one fact
 * written as many times as the graph has detectors.
 */
function CatalogueFooter() {
  return (
    <>
      <span className="min-w-0">Raised an open finding here. One raising nothing is absent, not zero.</span>
      <span className="min-w-0">Ordered by name, never by count.</span>
    </>
  )
}

const REGISTRY_HINT = (
  <InfoHint label="About the detector catalogue">
    A row exists only for a detector that has raised an open finding in this repository — the graph
    keeps no registry of which detectors are installed, only the findings they have written. A
    detector currently raising nothing does not appear, and that absence is indistinguishable from a
    detector that does not exist. Nothing here is a leaderboard: this screen carries no precision or
    accuracy figure, because detectors are not competing and a ratio computed from open findings
    alone, with no labelled corpus behind it, would measure nothing.
  </InfoHint>
)

const SCOPE_CHIP = (
  <ScopeChip scope="this workspace">
    Every figure on this screen counts open findings in this repository and in no other. A detector
    with no row here may still be raising findings elsewhere — this screen cannot tell you that,
    because it did not ask.
  </ScopeChip>
)

export function DetectorsPage() {
  // The route is the scope: this read `searchParams.get("repo_id")` while the route is
  // `/repositories/:repoId/detectors`, so an address naming a repository still rendered "Every
  // repository the index has seen".
  const { repoId } = useParams<{ repoId: string }>()
  const attribution = useDetectors(repoId)
  // The corpus answer, for the one question the roll-up cannot answer about its own emptiness.
  const corpusQuery = useOverview(repoId)
  const [openDetector, setOpenDetector] = useSelectionParam("detector")

  const rows = useMemo(() => attribution.data?.detectors ?? NO_ROWS, [attribution.data])
  const ids = useMemo(() => rows.map((row) => row.detector), [rows])
  useSelectionKeys(ids, openDetector, setOpenDetector)

  const corpus: CorpusAnswer | "unanswered" = corpusQuery.isSuccess
    ? { indexedAt: corpusQuery.data.indexed_at, hasIndexRun: corpusQuery.data.last_index_run !== null }
    : "unanswered"

  const ladder = useMemo(
    () => rungLadder(attribution.data?.by_rung ?? {}),
    [attribution.data],
  )
  const kinds = useMemo(() => claimKinds(rows), [rows])
  const selection = selectDetector(rows, openDetector)

  // Labelled "attributed", never "open": `total_open_findings` here and `severity_total` on
  // Findings count one population. Built for every query state — a band rendered only on success
  // shows "not asked yet" and "asked and empty" as the same nothing.
  const status: StatusSegment[] = attribution.isSuccess
    ? [
        {
          kind: "listing",
          label: "attributed",
          text:
            rows.length === 0
              ? `No open finding in ${repoId} is attributed to any detector.`
              : `${attribution.data.total_open_findings.toLocaleString()} open ${
                  attribution.data.total_open_findings === 1 ? "finding" : "findings"
                } in ${repoId}, attributed across ${rows.length} ${
                  rows.length === 1 ? "detector" : "detectors"
                }.`,
        },
        { kind: "note", text: OPEN_ONLY },
      ]
    : [
        {
          kind: "none",
          why: attribution.isError
            ? "the detector attribution did not answer"
            : "asking for the detector attribution",
        },
      ]

  const lastPass = corpusQuery.data?.last_index_run ?? null
  const kpis = (
    <KpiStrip
      items={[
        {
          label: "Detectors reporting",
          value: attribution.isSuccess ? (
            rows.length.toLocaleString()
          ) : attribution.isError ? (
            <Absent>not answered</Absent>
          ) : (
            <Pending />
          ),
          note: "detectors with an open finding here — the graph keeps no registry of the rest",
        },
        {
          label: "Kinds of change matched",
          value: attribution.isSuccess ? (
            kinds.length.toLocaleString()
          ) : attribution.isError ? (
            <Absent>not answered</Absent>
          ) : (
            <Pending />
          ),
          note: "distinct claim kinds across every detector here, not the targets they matched",
        },
        {
          label: "Rungs carrying evidence",
          value: attribution.isSuccess ? (
            `${ladder.carrying.length} of ${ladder.rows.filter((row) => row.known).length}`
          ) : attribution.isError ? (
            <Absent>not answered</Absent>
          ) : (
            <Pending />
          ),
          figure: false,
          note: "declared rungs with at least one open finding behind them; the rest were counted and found empty",
        },
        {
          label: "Last index pass",
          value: corpusQuery.isPending ? (
            <Pending />
          ) : corpusQuery.isError ? (
            <Absent>not answered</Absent>
          ) : lastPass === null ? (
            <Absent>no pass recorded</Absent>
          ) : (
            (formatTimestamp(lastPass.finished_at) ?? <Absent>still running</Absent>)
          ),
          figure: false,
          note: "the corpus these detectors fire against — a detector cannot fire against a repository nothing has read",
        },
      ]}
    />
  )

  if (repoId === undefined) return <UnknownRoute />

  if (attribution.isPending) {
    return (
      <ScreenFrame status={status} subtitle={QUESTION}>
        {kpis}
        <LoadingState what="detector attribution" />
      </ScreenFrame>
    )
  }

  if (attribution.isError) {
    return (
      <ScreenFrame status={status} subtitle={QUESTION}>
        {kpis}
        <ErrorState
          error={attribution.error}
          what="detector attribution"
          onRetry={() => void attribution.refetch()}
        />
      </ScreenFrame>
    )
  }

  const state = catalogueState({ detectorCount: rows.length, corpus })

  if (state !== "populated") {
    return (
      <ScreenFrame status={status} subtitle={QUESTION}>
        {kpis}
        <EmptyState
          headline={EMPTY_HEADLINE[state]}
          detail={EMPTY_DETAIL[state](repoId)}
          command={state === "never-indexed" ? `uv run sync index --repo ${repoId}` : undefined}
        />
        <p className="max-w-prose text-body text-ink-muted">
          A detector appears here only once it has raised an open finding — the graph keeps no
          registry of which detectors are installed. So one currently raising nothing does not
          appear, and that absence is indistinguishable from a detector that does not exist.
        </p>
      </ScreenFrame>
    )
  }

  return (
    <ScreenFrame layout="locked" status={status} subtitle={QUESTION}>
      {/* Portals into the chassis stats bar, so it costs the locked column no height. */}
      {kpis}

      {/* Four regions. Both tracks are declared: an implicit row is sized by its content before
          the `fr` rows divide what is left, which once collapsed two panes to 131px and 87px. */}
      <div
        className="grid min-h-0 min-w-0 flex-1 grid-cols-1 grid-rows-[repeat(4,minmax(0,1fr))] gap-section xl:grid-cols-[minmax(14rem,17rem)_minmax(24rem,1fr)_minmax(17rem,21rem)] xl:grid-rows-[minmax(0,3fr)_minmax(0,2fr)]"
      >
        <PanelPane
          className="xl:row-span-2"
          label="Detectors"
          icon={Radar}
          hint={REGISTRY_HINT}
          footer={<CatalogueFooter />}
          // Two lines rather than one `row-lg` strip: both are claims that may not scroll away.
          footerClassName="h-auto flex-col items-start gap-field py-row leading-tight"
        >
          <DetectorIndex rows={rows} selected={openDetector} onSelect={setOpenDetector} />
        </PanelPane>

        <PanelPane
          label={selection.state === "resolved" ? selection.row.detector : PANE_LABEL[selection.state]}
          icon={selection.state === "resolved" ? ScanSearch : Layers}
          actions={
            <>
              {SCOPE_CHIP}
              {selection.state === "none" ? null : (
                <button
                  type="button"
                  onClick={() => setOpenDetector(null)}
                  aria-label="Show every detector"
                  title="Show every detector"
                  className="rounded-control p-field text-ink-muted hover:bg-surface-subtle hover:text-ink focus:outline-none focus:ring-1 focus:ring-ring"
                >
                  <X aria-hidden="true" className="size-4" />
                </button>
              )}
            </>
          }
          bodyClassName="flex min-w-0 flex-col gap-section p-section"
        >
          {selection.state === "resolved" ? (
            <DetectorEvidence row={selection.row} repoId={repoId} />
          ) : selection.state === "unresolved" ? (
            <EmptyState
              headline="No detector in this roll-up carries that name."
              detail={`The address names ${selection.key}, and the read answered without it. Either it has raised nothing open in ${repoId}, or it is not a detector this deployment runs — the graph keeps no registry, so this screen cannot tell you which.`}
            />
          ) : (
            <EveryDetector rows={rows} total={attribution.data.total_open_findings} />
          )}
        </PanelPane>

        {/* Bare panes: each child brings its own card, so a banded header would be a second frame
            around one surface. `components/pane.tsx` carries the rule. */}
        <Pane>
          <PaneScroll>
            <RungLadder ladder={ladder} repoId={repoId} />
          </PaneScroll>
        </Pane>

        <Pane className="xl:col-span-2">
          <PaneScroll>
            <AutomationPanel repoId={repoId} />
          </PaneScroll>
        </Pane>
      </div>
    </ScreenFrame>
  )
}

/** The reading pane names the state it is in: an unresolved key is not the whole-set view. */
const PANE_LABEL: Record<string, string> = {
  none: "Every detector",
  unresolved: "Unknown detector",
  resolved: "Detector",
}

const EMPTY_HEADLINE: Record<string, string> = {
  "never-indexed": "Nothing has ever read this repository.",
  "counted-zero": "No open finding here is attributed to any detector.",
  "corpus-unknown": "No detector reported, and the corpus read has not answered.",
}

const EMPTY_DETAIL: Record<string, (repoId: string) => string> = {
  "never-indexed": (repoId) =>
    `A detector fires against a corpus, and no index pass and no call site in ${repoId} carries a ` +
    `read time. So this is not a detector that found nothing — there was nothing yet for one to ` +
    `look at.`,
  "counted-zero": (repoId) =>
    `The API answered and the graph holds no open finding in ${repoId} attributed to any ` +
    `detector. A counted zero: the corpus has been read, and nothing indexed here is currently ` +
    `flagged.`,
  "corpus-unknown": (repoId) =>
    `The roll-up answered with no detectors, and the read that would say whether ${repoId} has ` +
    `ever been indexed did not answer. So this screen cannot tell you whether nothing was found ` +
    `or nothing was ever looked at, and it will not guess between them.`,
}
