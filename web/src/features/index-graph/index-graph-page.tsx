/**
 * The indexing canvas as a page: `FileTreeCanvas` fed `GET /api/repositories/{repo_id}/graph`
 * through `useRepositoryGraph`, the same route `overview-graph-panel.tsx` draws its own copy of
 * the graph from.
 *
 * Scope comes from the route path parameter and never from a query string.
 *
 * **Two nothings, told apart.** This page used to render one empty state for both, and said so
 * in its own copy: "a repository the index never ran against shows the same nothing as one that
 * calls no vendor". That was honest about a payload that could not distinguish them.
 * `indexed_at` now can, and `index-state.ts` carries the classification — *never recorded* is
 * the canvas not being evidence about this codebase at all, and *indexed and found none* is a
 * measurement about it.
 *
 * **Off-path evidence is reported in every state, including the empty ones.** A repository whose
 * call sites were all retracted still holds observed traffic and unattributed findings, so
 * "nothing here" would drop what the graph is holding.
 *
 * **On `ScreenFrame`, with `fill`.** The canvas took its height from `100svh` minus a guess at
 * the chassis, which was measured against the old one and is wrong the moment a band above or
 * below it changes size. It now takes the height the frame's content band gives it.
 *
 * **The drawn count is stated in every state, not only when the picture is capped.** A count
 * that appears only on truncation makes its absence mean "all of it" by inference, which is the
 * silence this band exists to replace. The truncation caveat stays on the band beside it,
 * verbatim, and says what the count cannot: why the rest are not drawn.
 *
 * **The two controls sit on the surfaces they act on.** The re-read after a drop is the screen's
 * action, so it publishes into the frame's controls band; zoom and fit act on the canvas's own
 * d3 transform and stay on the canvas.
 *
 * **Registered at `/repositories/:repoId/graph`** (`lib/routes.ts`), level `Codebase`, `nav:
 * true` -- a rail destination, since it needs nothing beyond the selected workspace's own
 * `repoId` to build its address, the same test `routes.test.tsx` holds every such route to.
 * `overview-graph-panel.tsx` also links here directly, beside its own compact copy of this same
 * canvas. Lane B, which had exclusive ownership of `routes.ts`, was retired before registering
 * this; picked up once nothing else owned that file.
 */

import { useEffect } from "react"
import { useParams } from "react-router"

import { useRepositoryGraph } from "@/api/queries"
import type { RepositoryGraphResponse } from "@/api/types"
import { ErrorState, LoadingState } from "@/components/states"
import { Button } from "@/components/ui/button"

import { ApiTopologyCard } from "@/features/repositories/api-topology-card"
import { TopologyKpis } from "@/features/repositories/topology-kpis"
import { CouplingChord } from "@/features/index-graph/coupling-chord"
import { ForceMap } from "@/features/index-graph/force-map"
import { classifyIndexState, type IndexState } from "@/features/index-graph/index-state"
import { IndexStreamBanner } from "@/features/index-graph/index-stream-banner"
import { useRepositoryEvents } from "@/features/index-graph/use-repository-events"
import { OffPathNote } from "@/features/index-graph/off-path-note"
import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"
import { UnknownRoute } from "@/layouts/unknown-route"
import { formatTimestamp } from "@/lib/format"
import { describeRecordWindow } from "@/lib/record-window"

export interface IndexGraphPageProps {
  readonly question?: string
}

/**
 * The caveat the truncated picture carries, verbatim from the paragraph it replaces.
 *
 * Only the caveat moved: the count sentence beside it is now the band's records segment, which
 * states the same figure in every state rather than only this one.
 */
const TRUNCATION_CAVEAT =
  "The rest are indexed and reachable from the call-site tables; they are not drawn here " +
  "because the picture stops being legible before the codebase stops having edges."

/** What the graph read answered, once it has. Every figure here rests on that one read. */
function answeredStatus(
  graph: RepositoryGraphResponse,
  state: IndexState,
  arrived: StatusSegment
): StatusSegment[] {
  const segments: StatusSegment[] = [
    {
      kind: "records",
      label: "Call sites drawn",
      text: describeRecordWindow(
        0,
        graph.bindings.length,
        { count: graph.total_bindings, boundReached: false },
        "call site",
        "call sites"
      ),
    },
    {
      // `formatTimestamp` returns null exactly when `indexed_at` is null, so the absence marker
      // here is the payload's recorded nothing rather than a read that did not answer — which is
      // the collapse the scope beside it exists to refuse.
      kind: "figure",
      label: "Last indexed",
      value: formatTimestamp(graph.indexed_at),
      scope:
        graph.indexed_at === null
          ? "the graph answered and holds no call site ever recorded here — nothing records an index attempt, only its result"
          : "when the index last wrote a call site here; a retracted call site still proves it ran",
    },
    {
      kind: "figure",
      label: "Off path",
      value: state.offPathTotal.toLocaleString(),
      scope: "uncorrelated spans and unattributed findings the graph holds and no edge above draws",
    },
    arrived,
  ]
  if (graph.truncated) segments.push({ kind: "note", text: TRUNCATION_CAVEAT })
  return segments
}

export function IndexGraphPage() {
  const { repoId } = useParams<{ repoId: string }>()
  if (repoId === undefined) return <UnknownRoute />
  return <IndexGraphDetail repoId={repoId} />
}

function IndexGraphDetail({ repoId }: { repoId: string }) {
  const query = useRepositoryGraph(repoId)
  // The map leads: it is the view that answers "what does this codebase depend on" at a
  // glance, and the tree is the one a reader switches to for a path.

  // The canvas builds visibly and the banner accompanies it. Decision 87 protects a reader
  // *reading* a table; this is a surface you are *watching build*, and freezing it removes the
  // one moment the one-command install exists to create.
  const stream = useRepositoryEvents(repoId)

  // Each arrival re-reads the settled graph, so the picture grows from the same source of
  // truth every other screen uses rather than from a second one assembled off the wire. The
  // event says *something landed*; the read says *what the graph now holds*.
  useEffect(() => {
    if (stream.indexedCount === 0) return
    void query.refetch()
  }, [stream.indexedCount, query])

  const graph = query.data
  const state = graph === undefined ? null : classifyIndexState(graph)

  /**
   * The stream's own count, which answers on its own clock rather than the graph read's.
   *
   * Zero is a measurement here: the subscription is open and nothing has arrived. The scope
   * carries the wording the banner's docstring makes load-bearing — a window opened when the
   * reader did, never the run's total — and on a drop says the count is frozen without claiming
   * anything about whether the index is still going.
   */
  const arrived: StatusSegment = {
    kind: "figure",
    label: "Indexed since you opened this",
    value: stream.indexedCount.toLocaleString(),
    scope:
      stream.status === "dropped"
        ? "frozen when the live connection ended — what had arrived by then"
        : "counted since you opened this screen, not the run's total: a notification sent while nobody was listening is not queued",
  }

  // Built for every state the read can be in: a band that appears only on success renders "not
  // asked yet" and "asked, and this repository holds nothing" as the same blank strip.
  const status: StatusSegment[] =
    graph === undefined || state === null
      ? [
          {
            kind: "none",
            why: query.isError
              ? `the indexed graph for ${repoId} did not answer`
              : `asking for the indexed graph for ${repoId}`,
          },
        ]
      : answeredStatus(graph, state, arrived)

  /**
   * The re-read, offered rather than performed, in the band a reader looks in for an action.
   *
   * The sentence travels with the button: without it the control reads as a refresh, and what it
   * actually offers is the choice between a frozen live picture and a settled one. The refusal it
   * answers — the connection ended, and this screen cannot tell you whether the index continues —
   * stays whole in the banner below, which is the one thing this control must not be split from.
   */
  const controls =
    stream.status === "dropped" ? (
      <>
        <Button variant="outline" size="sm" onClick={() => void query.refetch()}>
          Load the settled graph
        </Button>
        <span className="text-meta text-ink-muted">
          — a complete answer you asked for, rather than one swapped in behind the frozen
          picture.
        </span>
      </>
    ) : undefined

  return (
    <ScreenFrame status={status} controls={controls} fill>
      <section className="flex min-h-0 min-w-0 flex-1 flex-col gap-8">
        {/* Above the read's own states rather than inside the answered one: a stream that drops
            while the first read is still in flight was previously invisible, and the control in
            the band above would then stand with the refusal it answers nowhere on screen. */}
        <IndexStreamBanner indexedCount={stream.indexedCount} status={stream.status} />

        {query.isPending && <LoadingState what={`the indexed graph for ${repoId}`} />}
        {query.isError && (
          <ErrorState
            error={query.error}
            what={`the indexed graph for ${repoId}`}
            onRetry={() => void query.refetch()}
          />
        )}

        {graph !== undefined && state !== null && (
          <>
            {/* The strip opens this page as it opens every other (owner ruling), and its subject is
                the map's: how wide the API surface this canvas draws actually is. Same key as the
                topology card below, so the pair is one read. */}
            <TopologyKpis repoId={repoId} />

            {state.kind === "never-recorded" && (
              <div className="flex flex-col gap-field rounded-surface border border-line bg-surface p-section">
                <h2 className="text-emphasis font-medium text-ink">
                  Nothing has ever been recorded for <span className="font-mono">{repoId}</span>.
                </h2>
                <p className="max-w-prose text-body text-ink-muted">
                  No call site has ever been written here. That is either an index that has not run
                  against this repository, or one that ran and found no vendor call — and nothing
                  records an index attempt, only its result, so this screen cannot tell you which. It is
                  not a finding that this codebase calls no vendor.
                </p>
                <OffPathNote graph={graph} total={state.offPathTotal} />
              </div>
            )}

            {state.kind === "indexed-empty" && (
              <div className="flex flex-col gap-field rounded-surface border border-line bg-surface p-section">
                <h2 className="text-emphasis font-medium text-ink">
                  Indexed, and holding no vendor call.
                </h2>
                <p className="max-w-prose text-body text-ink-muted">
                  The index last wrote a call site for <span className="font-mono">{repoId}</span> on{" "}
                  {formatTimestamp(state.indexedAt) ?? "a date it did not record"}, and none is current
                  now. This is a measurement rather than an absence of one: something looked here. A
                  repository whose calls have all since moved reads this way too, because a retracted
                  call site still proves the index ran.
                </p>
                <OffPathNote graph={graph} total={state.offPathTotal} />
              </div>
            )}

            {state.kind === "drawn" && (
              <>
                {/* The full graph takes the page, on the owner's direction: this route exists
                    because the Overview's panel is too small for a real codebase, so a canvas here
                    that was also boxed would be the same picture at the same size. The height comes
                    as a fraction of the window rather than a subtraction from the chassis. Not
                    from `flex-1`: `app-frame.tsx:565` sets `items-start` on the column, so there
                    is no spare height for a flex child to take, and with only `min-h-[32rem]` the
                    svg's 1200x700 viewBox drove the height off the canvas WIDTH -- measured losing
                    46% of its height at 1024x1200. The floor is what actually applies
                    against the old chassis and goes wrong whenever a band's height changes. */}
                <div className="min-h-[70svh] flex-1">
                  <ForceMap rows={graph.bindings} fill />
                </div>
                {/* This page's own analytics: the integration map's subject is what this codebase
                    calls, so the topology figures live here rather than on the Overview. The chord
                    beside them answers the one thing the topology card counts but cannot show --
                    *between which* integrations the coupling runs. */}
                <div className="grid auto-rows-fr gap-8 xl:grid-cols-2">
                  <ApiTopologyCard repoId={repoId} />
                  <CouplingChord repoId={repoId} />
                </div>
                <OffPathNote graph={graph} total={state.offPathTotal} />
              </>
            )}
          </>
        )}
      </section>
    </ScreenFrame>
  )
}
