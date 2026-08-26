/**
 * What this run *is*, spanning both panes and never scrolling.
 *
 * It replaces the narrow fact rail the screen used to hold beside a tabbed column. The rail's ten
 * facts did not disappear with it: four became top-bar tiles (`workflow-kpis.tsx`), the vendor's
 * route boundary became a clause in the evidence pane's opening entry, the three named-but-
 * impossible actions moved into the remediation pane's closing panel where the reference draws its
 * button bar, and what is left is here — the five that identify the run rather than describe it.
 *
 * **Three refusals travel with those facts and are restated rather than assumed.**
 *
 * There is no confidence figure and there will not be one. A reference incident view puts one in
 * exactly this position. What stands behind a claim on this console is the class of evidence it
 * rests on, and this run's evidence is named node by node in the pane below; the provenance rung
 * that records that class belongs to the API Dependency Graph, so the header links the finding
 * rather than inventing a rung the checkpointer cannot see.
 *
 * There is no outcome row. The outcome is the status band's own segment and the narrative's
 * closing entry, placed where the run stopped. A word for it here as well would be one fact at
 * three weights.
 *
 * **`Checkpoint span` is not a run duration**, and the meta row says so on screen. The top bar
 * carries the figure and can only hover its qualification, so a reader who never hovers would have
 * no way to tell what it covers. The claim is visible in the fewest honest words and the argument
 * for why the distinction exists sits behind the ⓘ — the owner's prose ruling of 2026-08-19.
 *
 * `dt`/`dd` semantics are deliberate: the labels are what a test can address without touching a
 * class name, and a run's identity genuinely is a set of term/definition pairs.
 */

import type { ReactNode } from "react"
import { Link } from "react-router"

import type { WorkflowState } from "@/api/types"
import { InfoHint } from "@/components/info-hint"
import { Absent, Formatted } from "@/components/status"
import { runIdentity } from "@/features/workflows/run-identity"
import { formatTimestamp } from "@/lib/format"
import { findingHref } from "@/lib/hrefs"

/**
 * Label beside value rather than above it, and the reason is the locked viewport.
 *
 * Stacked, five facts cost 76px of a pane budget of 681 at 1920×1080 — measured in Chrome. On one
 * baseline they cost half that, and the height goes to the panes, which are what a reader is
 * actually working in.
 */
function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex min-w-0 items-baseline gap-row">
      <dt className="furniture shrink-0 text-meta text-ink-muted">{label}</dt>
      <dd className="min-w-0 text-body">{children}</dd>
    </div>
  )
}

export function RunIdentityHeader({
  repoId,
  findingId,
  data,
  trailing,
}: {
  repoId: string
  findingId: string
  /**
   * Required, and the reason is that the caller has already answered for every other case: a
   * pending run, a 404 and a hard error each replace the whole split with their own state, so a
   * header rendered over no run is not a state this screen can reach. The spec's skeleton arm is
   * not built for that reason -- `CLAUDE.md`'s "build for the case that exists".
   */
  data: WorkflowState
  /** `FetchedAt` on a healthy read, `StaleBanner` on a failed refetch. The caller owns which. */
  trailing: ReactNode
}) {
  const identity = runIdentity(data)
  const terminal = data.outcome !== null && data.outcome !== "running"

  return (
    <header className="flex min-w-0 shrink-0 flex-col gap-row rounded-surface border border-line bg-card px-section py-row">
      <dl className="flex min-w-0 flex-wrap items-baseline gap-x-section gap-y-field">
        <Fact label="Run">
          <code className="font-mono text-meta break-all select-all">{data.thread_id}</code>
        </Fact>

        <Fact label="Finding">
          <Link to={findingHref(repoId, findingId)} className="underline underline-offset-2">
            <code className="font-mono text-meta break-all">{findingId}</code>
          </Link>
        </Fact>

        <Fact label="Repository">
          {data.repo_id === null ? (
            <Absent>the run recorded no repository</Absent>
          ) : (
            <code className="font-mono text-meta break-all">{data.repo_id}</code>
          )}
        </Fact>

        <Fact label="Started">
          {identity.startedAt == null ? (
            <Absent>no node has stamped a checkpoint yet</Absent>
          ) : (
            <time dateTime={identity.startedAt} className="font-mono text-meta">
              <Formatted value={formatTimestamp(identity.startedAt)} />
            </time>
          )}
        </Fact>

        <Fact label="Waiting on">
          {identity.waitingOn !== null ? (
            <span className="font-mono text-meta">{identity.waitingOn}</span>
          ) : terminal ? (
            // A finished run and a run still owing a node a visit are two different facts, and
            // the absence marker for both would let the first read as the second.
            <span className="text-ink-muted">Nothing — the run reached a terminal outcome.</span>
          ) : (
            <Absent>no node is marked due in the newest checkpoint</Absent>
          )}
        </Fact>
      </dl>

      {/* The qualification and the read instant share one meta row rather than the identity row.
          In the identity row the fact list wrapped and squeezed `FetchedAt` into four lines, which
          cost the panes 30px of a locked viewport for a sentence that fits on one. */}
      <div className="flex min-w-0 flex-wrap items-baseline justify-between gap-section">
        <p className="text-meta text-ink-muted">
          Checkpoint span is first checkpoint to last, not a run duration.{" "}
          <InfoHint label="About checkpoint span">
            A run waiting on the customer&#39;s CI writes no checkpoint for as long as that takes,
            and a run whose process has died writes the same nothing. &ldquo;How long it has been
            running&rdquo; is not derivable from this payload and is not derived.
          </InfoHint>
          {data.generation_count > 1 && (
            <>
              {" "}
              This is the most recent of {data.generation_count} runs the checkpointer holds for this
              finding.
            </>
          )}
        </p>

        <div className="min-w-0">{trailing}</div>
      </div>
    </header>
  )
}
