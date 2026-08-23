/**
 * The file tree, full screen, with this codebase's technical census beside it.
 *
 * **Owner ruling, 2026-08-19:** the Overview shows both maps small, and each opens into a page
 * that carries *its own* analytics. This page's subject is the codebase's shape — how it is laid
 * out, what it is made of, how old it is — so the census lives here rather than on the Overview.
 * The integration map's page carries the topology figures for the same reason.
 *
 * The tree fills the viewport, which is the reason this route exists separately from the
 * Overview's preview: the preview answers *what shape is this*, and the full view answers
 * *where is everything*.
 *
 * **The canvas has no height of its own any more.** It computed one as `100svh` minus the
 * opener's height, and that arithmetic was a copy of whatever the chassis happened to be that
 * week — wrong the day a band was added to it. It is a flex child of the filling content band
 * now, with a floor stated as a fraction of the window rather than as a subtraction from it.
 */

import { useQuery } from "@tanstack/react-query"
import { useParams } from "react-router"

import type { RepositoryGraphBinding } from "@/api/types"
import { useRepositoryGraph } from "@/api/queries"
import { ErrorState, LoadingState } from "@/components/states"
import {
  TreeMapControls,
  TreeMapSurface,
  useTreeMap,
} from "@/features/index-graph/tree-map-d3"
import { CodebaseFactsCard, fetchFacts } from "@/features/repositories/codebase-facts-card"
import { CodebaseFactsKpis } from "@/features/repositories/codebase-facts-kpis"
import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"
import { UnknownRoute } from "@/layouts/unknown-route"

/** Stable, so the hook's memos do not churn on every render before the graph answers. */
const NO_BINDINGS: RepositoryGraphBinding[] = []

/** What `sync.index.facts` records when the checkout had git and git answered. */
const GIT_CENSUS = "git ls-files"

export function FileTreePage() {
  const { repoId } = useParams<{ repoId: string }>()
  if (repoId === undefined) return <UnknownRoute />
  return <FileTreeDetail repoId={repoId} />
}

/**
 * The census qualifier, over the census that actually ran.
 *
 * `facts.census` is `git ls-files` where the checkout has git and git answered, and a filesystem
 * walk where either failed. Printing the git sentence over a walk would qualify the strip with a
 * measurement that did not happen, and an incorrect explanation of a gap is worse than none.
 */
function censusNote(census: string | null): StatusSegment[] {
  if (census === null) return []
  if (census === GIT_CENSUS) {
    return [
      {
        kind: "note",
        text:
          "Files and lines come from git ls-files and a newline count over bytes — what is " +
          "tracked, never what is on disk — so a generated directory that git ignores is absent " +
          "by design and an untracked scratch file does not inflate the count.",
      },
    ]
  }
  return [
    {
      kind: "note",
      text:
        `Files and lines come from a ${census} rather than git ls-files: this checkout's own ` +
        "list of tracked files was not available, so what the walk found is counted rather than " +
        "what is tracked.",
    },
  ]
}

/** Whose fold is on screen, and what a fold does and does not change about the picture. */
function foldNote(autoFitted: boolean): StatusSegment {
  return {
    kind: "note",
    text: autoFitted
      ? "Detail is fitted to this window: directories open by descending call-site weight until " +
        "the window is full. A folded directory carries its subtree's call sites, so folding " +
        "changes the picture's resolution and never its claims."
      : "The fold is yours from the first directory you touched, so detail is no longer fitted " +
        "to this window — Fit to window hands it back. A folded directory carries its subtree's " +
        "call sites, so folding changes the picture's resolution and never its claims.",
  }
}

function FileTreeDetail({ repoId }: { repoId: string }) {
  const query = useRepositoryGraph(repoId)
  // The census card and the strip below already issue this at this key, so the band states the
  // census on screen rather than opening a second request for it.
  const facts = useQuery({
    queryKey: ["codebase-facts", repoId],
    queryFn: ({ signal }) => fetchFacts(repoId, signal),
  })
  const map = useTreeMap(query.data?.bindings ?? NO_BINDINGS, true)

  const census = facts.isSuccess ? (facts.data.facts?.census ?? null) : null

  // Every figure here reads the graph and nothing else, and is stated only where the graph
  // answered — a zero drawn while the read is in flight would be a codebase with no call sites.
  const status: StatusSegment[] = query.isSuccess
    ? [
        {
          kind: "figure",
          label: "Nodes drawn",
          value: map.nodeCount.toLocaleString(),
          scope: "a folded directory is one node carrying its subtree's count",
        },
        {
          kind: "figure",
          label: "Call sites",
          value: map.callSites.toLocaleString(),
          scope: query.data.truncated
            ? `drawn, of ${query.data.total_bindings.toLocaleString()} the index holds — this picture is a subset`
            : "every call site the index recorded for this codebase",
        },
        {
          kind: "figure",
          label: "Zoom",
          value: `${map.zoomPercent}%`,
          scope:
            "100% draws the layout at its own scale; the canvas refits whenever the drawn tree changes",
        },
        foldNote(map.autoFitted),
        ...censusNote(census),
      ]
    : [
        {
          kind: "none",
          why: query.isError ? "the file tree did not answer" : "asking for the file tree",
        },
      ]

  return (
    <ScreenFrame
      status={status}
      controls={query.isSuccess ? <TreeMapControls map={map} /> : undefined}
      fill
    >
      <section className="flex min-h-0 flex-1 flex-col gap-8">

        {/* The strip opens this page as it opens every other (owner ruling). Its subject is
            the tree's -- how large this codebase is and what it is made of -- so it reads the
            same census the card at the foot of the page draws in full, on one key. */}
        <CodebaseFactsKpis repoId={repoId} />

        {query.isPending && <LoadingState what={`the file tree for ${repoId}`} />}
        {query.isError && (
          <ErrorState
            error={query.error}
            what={`the file tree for ${repoId}`}
            onRetry={() => void query.refetch()}
          />
        )}

        {query.isSuccess && (
          <>
            {/* The floor is doing all the work, and that is measured rather than assumed:
                `app-frame.tsx:565` sets `items-start` on the column, so there is no spare height
                for `flex-1` to take. It is a fraction of the window rather than a subtraction from
                the chassis, so no chassis change can make it wrong -- which is the whole reason
                the `100svh - 16rem` it replaced had to go. */}
            <div className="min-h-[70svh] flex-1">
              <TreeMapSurface map={map} />
            </div>
            {/* The census is this page's analytics: what the codebase is made of, measured with
                the index pass that produced the tree above it. */}
            <CodebaseFactsCard repoId={repoId} />
          </>
        )}
      </section>
    </ScreenFrame>
  )
}
