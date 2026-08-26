/**
 * The codebase map as a working surface: the canvas fills the frame and the mark you pick opens
 * an inspector beside it.
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
 * **Locked, on the owner's ruling of 2026-08-26.** The map fills the viewport and the page itself
 * never scrolls: the canvas owns pan and zoom, the inspector owns the one scrollbar in the dock,
 * and the API topology pair — which used to sit below the fold — opens as a drawer from the
 * controls band. A page-level scrollbar under a canvas that also scrolls is two answers to one
 * gesture.
 *
 * **The selection lives in the URL** as `?node=<ForceNode.id>`, so a reader hands a colleague the
 * mark they are looking at and Back closes the panel. The id is resolved against a fresh
 * `buildForceGraph` rather than held as an object, because a URL that survives a reload carries
 * an id and nothing else.
 *
 * **The two controls sit on the surfaces they act on.** The re-read after a drop is the screen's
 * action, so it publishes into the frame's controls band; zoom and fit act on the canvas's own
 * d3 transform and stay on the canvas.
 *
 * **Registered at `/repositories/:repoId/graph`** (`lib/routes.ts`), level `Codebase`, `nav:
 * false` — the Overview's map pane links here, and the palette finds it.
 */

import { useEffect, useMemo } from "react"
import { useParams } from "react-router"

import { useRepositoryGraph } from "@/api/queries"
import type { RepositoryGraphResponse } from "@/api/types"
import { DetailClose, useSelectionKeys, useSelectionParam } from "@/components/detail-layout"
import { ErrorState, LoadingState } from "@/components/states"
import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/vendor/supabase/ui/sheet"

import { ApiTopologyCard } from "@/features/repositories/api-topology-card"
import { TopologyKpis } from "@/features/repositories/topology-kpis"
import { CouplingChord } from "@/features/index-graph/coupling-chord"
import { buildForceGraph, ForceMap } from "@/features/index-graph/force-map"
import { GraphInspector, inspectorTitle } from "@/features/index-graph/graph-inspector"
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

/** A force layout has no linear order, so the arrow branch of the selection keys has nothing to
    walk; the hook is bound for Escape alone and returns early on an id it cannot find. */
const NO_ORDER: readonly string[] = []

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

  // The canvas builds visibly and the banner accompanies it. Decision 87 protects a reader
  // *reading* a table; this is a surface you are *watching build*, and freezing it removes the
  // one moment the one-command install exists to create.
  const stream = useRepositoryEvents(repoId)

  const [selectedId, setSelectedId] = useSelectionParam("node")
  useSelectionKeys(NO_ORDER, selectedId, setSelectedId)

  // Each arrival re-reads the settled graph, so the picture grows from the same source of
  // truth every other screen uses rather than from a second one assembled off the wire. The
  // event says *something landed*; the read says *what the graph now holds*.
  useEffect(() => {
    if (stream.indexedCount === 0) return
    void query.refetch()
  }, [stream.indexedCount, query])

  const graph = query.data
  const state = graph === undefined ? null : classifyIndexState(graph)

  const bindings = graph?.bindings
  const forceGraph = useMemo(
    () => (bindings === undefined ? null : buildForceGraph(bindings)),
    [bindings]
  )
  const selectedNode = forceGraph?.nodes.find((node) => node.id === selectedId) ?? null

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

  const drawn = state?.kind === "drawn" && graph !== undefined

  /**
   * The band a reader looks in for an action: the topology drawer, and a re-read after a drop.
   *
   * The re-read's sentence travels with its button — without it the control reads as a refresh,
   * and what it actually offers is the choice between a frozen live picture and a settled one. The
   * refusal it answers, that the connection ended and this screen cannot tell you whether the index
   * continues, stays whole in the banner below.
   */
  const controls =
    drawn || stream.status === "dropped" ? (
      <>
        {drawn && <TopologyDrawer repoId={repoId} />}
        {stream.status === "dropped" && (
          <>
            <Button variant="outline" size="sm" onClick={() => void query.refetch()}>
              Load the settled graph
            </Button>
            <span className="text-meta text-ink-muted">
              — a complete answer you asked for, rather than one swapped in behind the frozen
              picture.
            </span>
          </>
        )}
      </>
    ) : undefined

  return (
    <ScreenFrame status={status} controls={controls} layout="locked">
      {/* Above the read's own states rather than inside the answered one: a stream that drops
          while the first read is still in flight was previously invisible, and the control in
          the band above would then stand with the refusal it answers nowhere on screen. */}
      <div className="shrink-0">
        <IndexStreamBanner indexedCount={stream.indexedCount} status={stream.status} />
      </div>

      {drawn && graph !== undefined && state !== null ? (
        <>
          {/* The strip opens this page as it opens every other (owner ruling), and its subject is
              the map's: how wide the API surface this canvas draws actually is. Same key as the
              topology drawer, so the pair is one read. */}
          <TopologyKpis repoId={repoId} />

          {/* One band-height dock: the canvas takes what is left of the frame and the inspector
              takes a fixed column beside it. Below `xl` the inspector drops under the canvas at a
              fixed height rather than letting the column grow — a locked screen has no page
              scrollbar to catch the overflow. */}
          <div className="flex min-h-0 flex-1 flex-col gap-8 xl:flex-row">
            <div className="flex min-h-0 min-w-0 flex-1 flex-col">
              <ForceMap
                rows={graph.bindings}
                fill
                controls
                selectedId={selectedId}
                onSelect={(node) => setSelectedId(node === null ? null : node.id)}
              />
            </div>

            <aside
              aria-label="Node inspector"
              className="flex h-[22rem] shrink-0 flex-col overflow-hidden rounded-surface border border-line bg-surface xl:h-auto xl:w-[25rem]"
            >
              <header className="flex h-[var(--row-lg)] shrink-0 items-center gap-row border-b border-line bg-secondary px-section">
                <h2 className="min-w-0 truncate text-section" title={inspectorTitle(selectedNode)}>
                  {inspectorTitle(selectedNode)}
                </h2>
                {selectedNode !== null && (
                  <span className="ml-auto flex items-center">
                    <DetailClose onClose={() => setSelectedId(null)} />
                  </span>
                )}
              </header>
              {/* The only scroller in the dock. `overscroll-contain` stops a wheel that reaches the
                  end of this panel from chaining into the canvas behind it. */}
              <div className="flex min-h-0 flex-1 flex-col overflow-y-auto overscroll-contain p-section">
                <GraphInspector
                  repoId={repoId}
                  graph={graph}
                  node={selectedNode}
                  nodeCount={forceGraph?.nodes.length ?? 0}
                  offPathTotal={state.offPathTotal}
                />
              </div>
            </aside>
          </div>
        </>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col gap-8 overflow-auto">
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
            </>
          )}
        </div>
      )}
    </ScreenFrame>
  )
}

/**
 * The API topology pair, as a drawer rather than as a second screenful under the map.
 *
 * These two panels used to sit below the fold, which the locked layout no longer has. Neither is
 * dropped and neither moves into the 400px inspector — `ApiTopologyCard`'s breakpoints are
 * viewport-based, so a four-column grid inside a narrow pane renders four columns in 400px. The
 * drawer gives both the width they were drawn for, and `/graph` stays their only render site.
 */
function TopologyDrawer({ repoId }: { repoId: string }) {
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="outline" size="sm">
          API topology
        </Button>
      </SheetTrigger>
      {/* `size="lg"` rather than the default third of the viewport: `ApiTopologyCard`'s figure row
          is a four-column grid at `xl:`, which is a viewport breakpoint — at 640px the four
          columns are 142px each and the labels wrap. */}
      <SheetContent
        side="right"
        size="lg"
        className="flex flex-col gap-0 border-l border-line bg-surface p-0 sm:max-w-[56rem]"
      >
        <SheetHeader className="shrink-0 border-b border-line px-section py-row text-left">
          <SheetTitle className="text-section">API topology</SheetTitle>
          <SheetDescription className="text-meta text-ink-muted">
            Counted over every call site the index holds for {repoId}, not over the marks this map
            drew — a capped picture draws fewer than the figures here count.
          </SheetDescription>
        </SheetHeader>
        <div className="flex min-h-0 flex-1 flex-col gap-8 overflow-auto p-section">
          <ApiTopologyCard repoId={repoId} />
          <CouplingChord repoId={repoId} />
        </div>
      </SheetContent>
    </Sheet>
  )
}
