/**
 * One run's record, as the drawer's body.
 *
 * `DetailLayout` owns the frame, the title and the close control; this is only what goes inside,
 * exactly as `call-site-drawer.tsx` is for call sites.
 *
 * **There is no second request and therefore no loading state.** Say it here so nobody adds a
 * spinner for a fetch that does not happen: the stream already holds this row, and the node-by-node
 * story a `useWorkflow` read would give belongs to the workflow screen, which this links to rather
 * than reproducing.
 *
 * Everything the stream had to drop to keep one line per row lands here — the finding id, the
 * liveness chip, the abandon reason, the thread and run identifiers — plus the stored row itself.
 */

import { Link } from "react-router"

import type { RunRow } from "@/api/types"
import { FactList, type Fact } from "@/components/fact-list"
import { InfoHint } from "@/components/info-hint"
import { RelativeTime } from "@/components/relative-time"
import { Absent, Formatted } from "@/components/status"
import { OutcomeTag, Tag } from "@/components/tag"
import { AbandonReason } from "@/features/runs/abandon-reason"
import { describeOutcome, isRehearsal } from "@/features/runs/run-row"
import { orAbsent } from "@/lib/format"

/** Liveness as a recorded word (B194) — a closed vocabulary, neutral, legible without its box. */
const LIVENESS_WORD: Record<NonNullable<RunRow["liveness"]>, string> = {
  alive: "process alive",
  expired: "heartbeats stopped",
  unmonitored: "not monitored",
}

/**
 * The stored row, verbatim, in two ink levels.
 *
 * The honest form of the reference's JSON payload panel: the actual object the API sent, nothing
 * invented. Keys take the muted ink and values the primary one — a split, not a syntax highlight.
 * The reference's four `json-*` hues would each need a row in `DESIGN.md` with contrast arithmetic
 * against 5.05:1, bought for a colouring nobody asked for.
 */
function StoredRecord({ run }: { run: RunRow }) {
  const lines = JSON.stringify(run, null, 2).split("\n")
  return (
    <details className="rounded-surface border border-line">
      <summary className="furniture cursor-pointer px-row py-row text-meta text-ink-muted">
        The stored record, verbatim
      </summary>
      <pre className="max-h-80 overflow-auto border-t border-line px-row py-row font-mono text-meta leading-relaxed text-ink">
        {lines.map((line, index) => {
          const key = /^(\s*)("(?:[^"\\]|\\.)*":)(.*)$/.exec(line)
          return (
            <div key={index}>
              {key === null ? (
                <span className="text-ink-muted">{line}</span>
              ) : (
                <>
                  <span className="text-ink-muted">
                    {key[1]}
                    {key[2]}
                  </span>
                  {key[3]}
                </>
              )}
            </div>
          )
        })}
      </pre>
    </details>
  )
}

export function RunRecordDetail({ run }: { run: RunRow }) {
  const rehearsal = isRehearsal(run)

  const facts: Fact[] = [
    { label: "Outcome", value: <OutcomeTag outcome={describeOutcome(run.outcome, rehearsal)} /> },
    { label: "Kind", value: <span className="font-mono">{rehearsal ? "rehearsal" : "live"}</span> },
    {
      label: "Node the graph owes",
      // Two different nothings, and the bare marker rendered them as one. `current_node` is
      // non-null exactly while a run is unfinished, so on a terminal run there is no node to owe
      // -- while an in-flight run with no node is a checkpoint that dropped the field, which is a
      // gap in the record rather than a property of the run.
      value:
        run.current_node !== null && run.current_node !== "" ? (
          <span className="font-mono">{run.current_node}</span>
        ) : run.outcome === null ? (
          <Absent>no node recorded</Absent>
        ) : (
          <Absent>the run finished — it owes no node</Absent>
        ),
    },
    {
      label: "Last checkpoint",
      value: (
        <span className="inline-flex items-center gap-field font-mono">
          <RelativeTime iso={run.last_checkpoint_at} />
          <InfoHint label="About the last checkpoint">
            A checkpoint records progress, not existence — &ldquo;last checkpoint&rdquo; is
            staleness, not liveness. A run parked at <code className="font-mono">await_ci</code>{" "}
            blocks inside that node while it waits on the customer&rsquo;s CI, and writes no
            checkpoint for as long as that takes, by design. What tells that run apart from one
            that died is the heartbeat below: the runner&rsquo;s process says &ldquo;still
            here&rdquo; on a timer, straight through a CI wait, and a run whose heartbeats stop
            with no clean exit is recorded <span className="font-mono">expired</span> by a sweep —
            a stored state change, not a guess made at render time.
          </InfoHint>
        </span>
      ),
    },
    {
      label: "Liveness",
      value:
        run.liveness === null ? (
          // Never "not monitored", which is a different recorded value: a terminal run is one
          // liveness was never a question about.
          <Absent>terminal run — liveness is not a question</Absent>
        ) : (
          <span className="inline-flex flex-wrap items-center gap-field">
            <Tag>{LIVENESS_WORD[run.liveness]}</Tag>
            {run.last_heartbeat_at !== null && (
              <span className="font-mono text-meta text-ink-muted">
                <RelativeTime iso={run.last_heartbeat_at} />
              </span>
            )}
          </span>
        ),
    },
    {
      label: "Workspace",
      value:
        run.repo_id === null ? (
          <Absent>the checkpoint names no repository</Absent>
        ) : (
          <span className="font-mono break-all">{run.repo_id}</span>
        ),
    },
    { label: "Finding id", value: <span className="font-mono break-all">{run.finding_id}</span> },
    { label: "Thread", value: <span className="font-mono break-all">{run.thread_id}</span> },
    {
      label: "Run",
      value: (
        <span className="font-mono break-all">
          <Formatted value={orAbsent(run.run_id)} />
        </span>
      ),
    },
  ]

  return (
    <div className="flex flex-col gap-section">
      <FactList facts={facts} />

      {run.outcome === "abandoned" && (
        <section className="flex flex-col gap-field">
          <h3 className="furniture text-meta text-ink-muted">Why it gave up</h3>
          {/* Unclamped by the pane rather than by the component: this is where a reason a
              thousand pixels tall can finally be read, because the pane scrolls. */}
          <AbandonReason reason={run.abandon_reason} />
        </section>
      )}

      {run.repo_id === null ? (
        <p className="text-body text-ink-muted">
          There is no link to this run&rsquo;s workflow: the checkpoint names no repository, and a
          workflow address is workspace-scoped. Guessing one would send you to another
          customer&rsquo;s finding.
        </p>
      ) : (
        <Link
          to={`/repositories/${encodeURIComponent(run.repo_id)}/findings/${encodeURIComponent(run.finding_id)}/workflow`}
          className="text-body underline underline-offset-2"
        >
          Open this finding&rsquo;s workflow, node by node
        </Link>
      )}

      <StoredRecord run={run} />
    </div>
  )
}
