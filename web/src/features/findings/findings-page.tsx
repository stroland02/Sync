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
 */

import { useParams } from "react-router"

import { useWorkspaceFindings } from "@/api/queries"
import type { FindingOrder } from "@/api/types"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { MetricPanel } from "@/components/metric-panel"
import { FindingsTable } from "@/features/findings/findings-table"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { FooterBar } from "@/layouts/footer-bar"
import { UnknownRoute } from "@/layouts/unknown-route"
import { useFilterParam } from "@/lib/use-filter-param"
import { useOffsetParam } from "@/lib/use-offset-param"

const OFFSET_KEY = "findings_offset"
const DEFAULT_LIMIT = 25

const QUESTION = "Every open finding in this workspace, and what each one is bound to."

export function FindingsPage() {
  const { repoId } = useParams<{ repoId: string }>()
  const [offset, setOffset] = useOffsetParam(OFFSET_KEY)
  const [severity] = useFilterParam("severity")
  const [order] = useFilterParam("order")

  const query = useWorkspaceFindings(repoId ?? "", {
    limit: DEFAULT_LIMIT,
    offset,
    severity: severity ?? undefined,
    order: (order ?? undefined) as FindingOrder | undefined,
  })

  if (repoId === undefined) return <UnknownRoute />

  return (
    <section className="flex flex-col gap-section min-w-0">
      <div className="flex flex-col gap-field">
        <Breadcrumbs
          trail={[
            { label: repoId, to: `/repositories/${encodeURIComponent(repoId)}` },
            { label: "Findings" },
          ]}
        />
        <p className="text-meta text-muted-foreground">{QUESTION}</p>
      </div>

      {query.isPending ? (
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
          offset={offset}
          onOffset={setOffset}
          busy={query.isFetching}
          filtered={severity !== null}
        />
      )}
    </section>
  )
}

function FindingsBody({
  repoId,
  page,
  offset,
  onOffset,
  busy,
  filtered,
}: {
  repoId: string
  page: NonNullable<ReturnType<typeof useWorkspaceFindings>["data"]>
  offset: number
  onOffset: (next: number) => void
  busy: boolean
  /** Whether a narrowing is applied, which is what makes the two totals differ. */
  filtered: boolean
}) {
  if (page.items.length === 0) {
    return (
      <EmptyState
        headline={`No open finding in ${repoId}.`}
        // Absence apart from zero. The two cases below are the same empty table and entirely
        // different facts, and the payload already knows which one this is.
        detail={
          page.indexed_at === null
            ? `Nothing has indexed ${repoId}, so this is not a count of zero — it is the absence of a measurement. A finding appears here once INDEX has walked this workspace and a detector has run against what it found.`
            : `${repoId} was indexed, and no detector has an open finding against it. That is a measured zero rather than an unanswered question.`
        }
      />
    )
  }

  return (
    <div className="flex flex-col gap-section min-w-0">
      <MetricPanel
        label="Errors and incidents"
        metric={{
          value: page.severity_total.toLocaleString(),
          // The scope travels with the figure. A total that does not say what it counted over is
          // the claim-about-everything this console refuses.
          unit: `open ${page.severity_total === 1 ? "finding" : "findings"} in ${repoId}`,
        }}
        caption={
          <p className="max-w-prose">
            Call sites that an open finding touches in{" "}
            <span className="font-mono">{repoId}</span>, and in no other workspace. The rung on each
            row says how the system knows the site is bound to the operation, and the ordering
            applied is the one the API says it applied rather than the one the address asked for.
          </p>
        }
      >
        <FindingsTable repoId={repoId} rows={page.items} />
        {/* Decision 60: with a filter on, `total` counts the narrowed set while `severity_total`
            counts the scope, and a bare range under a narrowed table reads as the whole set. */}
        <FooterBar
          offset={offset}
          limit={DEFAULT_LIMIT}
          shown={page.items.length}
          total={page.total}
          nextOffset={page.next_offset}
          busy={busy}
          unfilteredTotal={filtered ? page.severity_total : undefined}
          onOffsetChange={onOffset}
        />
      </MetricPanel>
    </div>
  )
}
