/**
 * Findings: what is broken in this workspace.
 *
 * **The console did not have this screen.** Five destinations sat in the rail — Overview, API
 * services, Vendors, Signals, Detectors — and a finding was reachable only by drilling through one
 * of them. An operator arriving with the question the product exists to answer, *what is broken
 * here*, had nowhere to go. `GET /api/repositories/{repo_id}/findings` had existed since the
 * transport was written and nothing had ever called it, because the only hook for this payload
 * demanded a vendor id.
 *
 * It sits at the specification's own `Finding` level rather than claiming a new one, so
 * `GRAPH_LEVELS` is untouched: a list of findings is an aggregate over findings, and
 * `.claude/rules/console-hierarchy.md` is explicit that an aggregate is not a rung.
 *
 * ## What is stated rather than assumed
 *
 * **The count names its scope.** The `codebases-panel` defect in its general form is a figure
 * printed without what it was counted over, which reads as a claim about everything. Every total
 * here says the workspace it belongs to.
 *
 * **An empty list is not a clean bill of health.** *No open findings* on its own is the exact
 * collapse of absence into zero this console exists to refuse: it reads identically whether the
 * detectors ran and found nothing, or nothing has ever indexed this workspace. The empty state
 * says which, from the payload's own `indexed_at`.
 *
 * **The rung is a column.** Every row carries the rung its binding came from — `static`,
 * `resolved` or `observed` — because a false positive that cannot be attributed to a rung cannot
 * be fixed. It is not hideable and it is not a badge colour.
 *
 * **No severity ordering is invented here.** `severity_order` arrives in the payload because it is
 * a declared judgement rather than something the graph stores, and a copy of it in this file would
 * eventually be the wrong copy.
 *
 * ## Triage header, 2026-08-18
 *
 * The severity narrowing was a URL parameter with no control — a reader could arrive at a
 * narrowed table but never narrow one. `TriageTabs` is that control: one tab per kind in the
 * payload's own order, counted over the scope rather than the page, with the whole-scope tab
 * first. Its empty states carry the absence-apart-from-zero distinction this file used to make
 * page-wide, sharpened per-tab and naming the detectors that stood behind a measured zero.
 */

import { useParams } from "react-router"

import { useChangeUnits, useDetectors, useTickets, useWorkspaceFindings } from "@/api/queries"
import { POLL_MS } from "@/features/tickets/ticket-action"
import { ChangeUnitGroups } from "@/features/findings/change-unit-groups"
import type { FindingOrder } from "@/api/types"
import { InfoHint } from "@/components/info-hint"
import { PageTabs, findingsTabs } from "@/components/page-tabs"
import { DismissedTally } from "@/features/findings/dismissed-tally"
import { FindingsKpis } from "@/features/findings/findings-kpis"
import { ErrorState, LoadingState } from "@/components/states"
import { MetricPanel } from "@/components/metric-panel"
import {
  TriageTabs,
  type TriageChecks,
  type TriageTab,
} from "@/components/triage-tabs"
import { FindingsTable } from "@/features/findings/findings-table"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { FooterBar } from "@/layouts/footer-bar"
import { UnknownRoute } from "@/layouts/unknown-route"
import { useFilterParam } from "@/lib/use-filter-param"
import { useOffsetParam } from "@/lib/use-offset-param"

const OFFSET_KEY = "findings_offset"
const DEFAULT_LIMIT = 25

/** The tab for the whole scope. Not a severity value, so it cannot collide with one. */
const ALL_TAB = "all"

const QUESTION = "Every open finding in this workspace, and what each one is bound to."

export function FindingsPage() {
  const { repoId } = useParams<{ repoId: string }>()
  const [offset, setOffset] = useOffsetParam(OFFSET_KEY)
  // The severity tab changes which rows exist, so the offset measured against the old set is
  // cleared in the same URL write — `use-filter-param`'s own reasoning, previously unapplied here.
  const [severity, setSeverity] = useFilterParam("severity", [OFFSET_KEY])
  const [order] = useFilterParam("order")

  const query = useWorkspaceFindings(repoId ?? "", {
    limit: DEFAULT_LIMIT,
    offset,
    severity: severity ?? undefined,
    order: (order ?? undefined) as FindingOrder | undefined,
  })
  // For the triage header's `checks`: an empty tab must say which detectors stood behind the
  // zero, and the findings payload does not carry their names — the detector roll-up does.
  const detectors = useDetectors(repoId)

  if (repoId === undefined) return <UnknownRoute />

  return (
    <section className="flex min-w-0 flex-col gap-8">
      <div className="flex flex-col gap-field">
        {/* Level name only: the scope trail in the top bar already draws the repository, and
            M7-W195 trimmed exactly this repetition from five other routes. */}
        <Breadcrumbs trail={[{ label: "Findings" }]} />
        <PageTabs label="Findings" tabs={findingsTabs(repoId)} />
        <p className="text-meta text-muted-foreground">{QUESTION}</p>
      </div>

      {/* Dashboard F1. The page's opening row, above everything else (owner direction
          2026-08-19): it carries what the tabs and the table do not -- how many detectors stood
          behind the answer, and when this workspace was last indexed, which is what makes an
          empty table readable as clean rather than as unchecked. */}
      {query.isSuccess && (
        <FindingsKpis
          page={query.data}
          detectorNames={
            detectors.isSuccess ? detectors.data.detectors.map((row) => row.detector) : null
          }
        />
      )}

      {/* What a human has already ruled on, beside what is still open. The table below lists
          open findings only, so without this a finding somebody deliberately set aside reads
          as one nobody has looked at. It states its own fleet scope, which is why it can sit
          on a workspace-scoped screen at all. */}
      <DismissedTally />

      {query.isPending || detectors.isPending ? (
        <LoadingState what={`open findings in ${repoId}`} />
      ) : query.isError ? (
        <ErrorState
          error={query.error}
          what={`open findings in ${repoId}`}
          onRetry={() => void query.refetch()}
        />
      ) : (
        <FindingsBody
          repoId={repoId}
          page={query.data}
          detectorNames={
            detectors.isSuccess ? detectors.data.detectors.map((row) => row.detector) : null
          }
          offset={offset}
          onOffset={setOffset}
          busy={query.isFetching}
          severity={severity}
          onSeverity={setSeverity}
        />
      )}
    </section>
  )
}

function FindingsBody({
  repoId,
  page,
  detectorNames,
  offset,
  onOffset,
  busy,
  severity,
  onSeverity,
}: {
  repoId: string
  page: NonNullable<ReturnType<typeof useWorkspaceFindings>["data"]>
  /** The detector roll-up's names, or null when that route did not answer. */
  detectorNames: string[] | null
  offset: number
  onOffset: (next: number) => void
  busy: boolean
  severity: string | null
  onSeverity: (next: string | null) => void
}) {
  // The tab vocabulary is the payload's own `severity_order`, most severe first, with any kind
  // the counts hold beyond it appended rather than dropped — a row whose kind the tabs omit is
  // unreachable by exactly the reader triaging it. A kind at zero keeps its tab: the counts are
  // computed without the severity narrowing, so zero is a measured answer, not an absence.
  // M15 Task 7: the change leads, because one vendor change breaking eleven call sites is one
  // decision rather than eleven, and a flat list is the console asserting otherwise by its shape.
  // The parameter spells only the departure from the default, so an unswitched screen's URL is
  // the URL it had before the toggle existed.
  const [view, setView] = useFilterParam("findings_view", ["findings_offset"])
  const grouped = view !== "flat"

  const kinds = [
    ...page.severity_order,
    ...Object.keys(page.severity_counts).filter((kind) => !page.severity_order.includes(kind)),
  ]
  const tabs: TriageTab[] = [
    {
      id: ALL_TAB,
      label: "every kind",
      count: { kind: "counted", value: page.severity_total },
    },
    ...kinds.map(
      (kind): TriageTab => ({
        id: kind,
        label: kind,
        count: { kind: "counted", value: page.severity_counts[kind] ?? 0 },
      }),
    ),
  ]

  // Absence apart from zero, per tab now rather than per page: an unindexed workspace has not
  // been checked at all, an indexed one names the detectors that stood behind its zeros. The
  // roll-up failing to answer is stated as its own fact — claiming "checked" on its behalf
  // would put a sentence on screen nothing computed.
  const checks: TriageChecks =
    page.indexed_at === null
      ? {
          kind: "unchecked",
          why: `Nothing has indexed ${repoId}, so no detector has had anything to run against. A finding appears here once INDEX has walked this workspace.`,
        }
      : detectorNames === null
        ? {
            kind: "unchecked",
            why: `${repoId} was indexed, but the detector roll-up did not answer, so this screen cannot name what checked it.`,
          }
        : detectorNames.length === 0
          ? {
              kind: "unchecked",
              why: `${repoId} was indexed and the detector roll-up lists nothing for it — no detector has reported over this workspace yet.`,
            }
          : {
              kind: "checked",
              ran: [detectorNames[0], ...detectorNames.slice(1)],
              at: page.indexed_at,
            }

  return (
    <TriageTabs
      legend="Findings by kind"
      noun="open findings"
      tabs={tabs}
      activeId={severity ?? ALL_TAB}
      onSelect={(id) => onSeverity(id === ALL_TAB ? null : id)}
      checks={checks}
    >
      <MetricPanel
        label="Errors and incidents"
        // Explanation moves behind the ⓘ (owner direction 2026-08-18); the scope stays in the
        // unit string, because a count that does not say what it counted over is the
        // claim-about-everything this console refuses, and a tooltip is a disclosure.
        hint={
          <InfoHint label="About errors and incidents">
            Call sites that an open finding touches in this workspace, and in no other. The rung
            on each row says how the system knows the site is bound to the operation, and the
            ordering applied is the one the API says it applied rather than the one the address
            asked for.
          </InfoHint>
        }
        metric={{
          value: page.severity_total.toLocaleString(),
          unit: `open ${page.severity_total === 1 ? "finding" : "findings"} in ${repoId}`,
        }}
      >
        {/* The severity tab reaches both views, because the grouping narrows before it buckets.
            A tab that stopped applying when the view changed would look active over numbers
            true of something else. */}
        <GroupingToggle grouped={grouped} onChange={setView} />
        {grouped ? (
          <GroupedFindings repoId={repoId} severity={severity} />
        ) : (
          <FlatFindings
            repoId={repoId}
            page={page}
            offset={offset}
            onOffset={onOffset}
            busy={busy}
            severity={severity}
          />
        )}
      </MetricPanel>
    </TriageTabs>
  )
}

/** The flat list and its own ticket read, mounted only while this is the view on screen. */
function FlatFindings({
  repoId,
  page,
  offset,
  onOffset,
  busy,
  severity,
}: {
  repoId: string
  page: NonNullable<ReturnType<typeof useWorkspaceFindings>["data"]>
  offset: number
  onOffset: (next: number) => void
  busy: boolean
  severity: string | null
}) {
  // One read for the whole table; the cells classify against it rather than each asking again.
  const ticketsQuery = useTickets(repoId, null, { refetchIntervalMs: POLL_MS })

  return (
    <>
      <FindingsTable
        repoId={repoId}
        rows={page.items}
        tickets={ticketsQuery.isSuccess ? ticketsQuery.data.tickets : null}
      />
      {/* Decision 60: with a filter on, `total` counts the narrowed set while `severity_total`
          counts the scope, and a bare range under a narrowed table reads as the whole set. */}
      <FooterBar
        offset={offset}
        limit={DEFAULT_LIMIT}
        shown={page.items.length}
        total={page.total}
        nextOffset={page.next_offset}
        busy={busy}
        unfilteredTotal={severity !== null ? page.severity_total : undefined}
        onOffsetChange={onOffset}
      />
    </>
  )
}

/** Which of the two questions this screen answers, held in the URL so it can be handed over. */
function GroupingToggle({
  grouped,
  onChange,
}: {
  grouped: boolean
  onChange: (next: string | null) => void
}) {
  return (
    <div className="flex items-center gap-field">
      {[
        { id: "units", label: "By change", on: grouped },
        { id: "flat", label: "Every finding", on: !grouped },
      ].map((choice) => (
        <button
          key={choice.id}
          type="button"
          aria-pressed={choice.on}
          onClick={() => onChange(choice.id === "units" ? null : "flat")}
          className={`rounded-control border px-field py-field text-meta transition-colors ${
            choice.on
              ? "border-line bg-surface-subtle text-ink"
              : "border-transparent text-ink-muted hover:text-ink"
          }`}
        >
          {choice.label}
        </button>
      ))}
    </div>
  )
}

/** The grouped view and its own read, on its own key. */
function GroupedFindings({ repoId, severity }: { repoId: string; severity: string | null }) {
  const units = useChangeUnits({ repoId, severity })

  if (units.isPending) return <LoadingState what={`the changes open in ${repoId}`} />
  if (units.isError) {
    return (
      <ErrorState
        error={units.error}
        what={`the changes open in ${repoId}`}
        onRetry={() => void units.refetch()}
      />
    )
  }
  return <ChangeUnitGroups repoId={repoId} units={units.data.items} unitTotal={units.data.total} />
}
