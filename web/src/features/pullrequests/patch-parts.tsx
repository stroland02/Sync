/**
 * The pieces of a patch, rendered the same way wherever a patch is shown.
 *
 * These were private to `patch-panel.tsx` while the Pull Request level was the only screen that
 * drew a diff. The Solution Workflow's remediation pane is the second use, which is where
 * `CLAUDE.md` says to factor — and the alternative was two implementations of a diff renderer
 * disagreeing about how many lines it truncates at.
 *
 * A pure move. `pull-request-page.test.tsx` staying green with no edits is the proof: if it needed
 * one, this stopped being an extraction and became a rewrite.
 *
 * **The diff carries no colour, and that is a decision rather than an omission.** A red-and-green
 * diff needs two token values with contrast arithmetic behind them, `DESIGN.md` is the token
 * contract, and inventing a value there is the one thing a lane may not do on its own. Until then
 * the marker column carries the fact, which is legible without colour and is the property every
 * state on this console has to hold anyway.
 *
 * **The horizontal scroll belongs to the diff container and never to the page body.** `min-w-0` is
 * what makes that true rather than intended — without it the scroller keeps a min-content floor
 * inside its flex parent, a long source line pushes the parent wider, and the page scrolls while
 * this box never does.
 */

import type { PatchResponse, WorkflowNode } from "@/api/types"
import { Absent } from "@/components/status"
import { verificationChain } from "@/features/pullrequests/verification-chain"

/** How much of a diff is shown before the reader is told there is more. */
export const VISIBLE_DIFF_LINES = 60

/**
 * One diff line, keeping its marker.
 *
 * The marker is the whole signal here, so it sits in its own column rather than being left at the
 * head of the text where a wrapped line would hide it. Context lines are muted because they are
 * the parts that did not change; that is a statement about the content, not a decoration.
 */
function DiffLine({ line }: { line: string }) {
  const marker = line.startsWith("+") ? "+" : line.startsWith("-") ? "-" : " "
  const changed = marker !== " "
  return (
    <li className="flex min-w-0 items-baseline gap-row whitespace-pre">
      <span className="w-3 shrink-0 select-none font-mono text-meta text-ink-muted">{marker}</span>
      <span className={`min-w-0 font-mono text-meta ${changed ? "" : "text-ink-muted"}`}>
        {line.slice(marker === " " ? 0 : 1)}
      </span>
    </li>
  )
}

/** The diff, in a scroller of its own. */
export function Diff({ diff }: { diff: string }) {
  const lines = diff.split("\n")
  const shown = lines.slice(0, VISIBLE_DIFF_LINES)
  const hidden = lines.length - shown.length

  return (
    <div className="flex min-w-0 flex-col gap-row">
      <ol className="min-w-0 overflow-x-auto rounded-surface border border-line py-field">
        {shown.map((line, index) => (
          <DiffLine key={index} line={line} />
        ))}
      </ol>
      {/* A truncation the reader cannot see is a diff of sixty lines reading as the whole change.
          The count is stated rather than implied by a fade. */}
      {hidden > 0 && (
        <p className="text-meta text-ink-muted">
          Showing the first {VISIBLE_DIFF_LINES} lines of {lines.length}. The remaining {hidden} are
          on the branch named above.
        </p>
      )}
    </div>
  )
}

/** The counts, derived from the diff rather than stored beside it. */
export function PatchStat({ stat }: { stat: PatchResponse["stat"] }) {
  if (stat === null) return null
  return (
    <p className="font-mono text-meta">
      {stat.files_changed} {stat.files_changed === 1 ? "file" : "files"} changed
      <span className="text-ink-muted"> · </span>+{stat.lines_added}
      <span className="text-ink-muted"> · </span>−{stat.lines_removed}
    </p>
  )
}

/** Where the change went. Rendered even when it went nowhere, because that is the fact. */
export function PatchTargetList({ target }: { target: PatchResponse["target"] }) {
  return (
    <dl className="flex min-w-0 flex-col gap-field">
      <div className="flex min-w-0 items-baseline gap-row">
        <dt className="shrink-0 text-meta text-ink-muted">Repository</dt>
        <dd className="min-w-0 font-mono text-meta break-words">
          {target.repo_id ?? <Absent>the run recorded no repository</Absent>}
        </dd>
      </div>
      <div className="flex min-w-0 items-baseline gap-row">
        <dt className="shrink-0 text-meta text-ink-muted">Branch</dt>
        <dd className="min-w-0 font-mono text-meta break-words">
          {target.branch ?? <Absent>this patch was never pushed</Absent>}
        </dd>
      </div>
    </dl>
  )
}

/**
 * The chain, as two named checks rather than one verdict.
 *
 * Two checks are reported as two checks. Averaging them into a single figure would put "we could
 * not check" on the same axis as "we checked and it passed", which is the collapse this console
 * was built to replace, and it is refused here as everywhere else.
 */
export function VerificationChain({ nodes }: { nodes: WorkflowNode[] }) {
  return (
    <ol className="flex min-w-0 flex-col">
      {verificationChain(nodes).map((check, index) => (
        <li
          key={check.label}
          className={`min-w-0 py-field ${index === 0 ? "" : "border-line border-t"}`}
        >
          <div className="flex min-w-0 flex-wrap items-baseline gap-row">
            <h3 className="text-body font-medium">{check.label}</h3>
            {/* The state is a recorded value from a closed vocabulary and reads without its
                colour, which is what `CLAUDE.md` permits. It is not a light and not a dot. */}
            <span className="font-mono text-meta">{check.state.replace("_", " ")}</span>
          </div>
          <p className="mt-field max-w-prose text-body text-ink-muted">{check.detail}</p>
        </li>
      ))}
    </ol>
  )
}
