/**
 * The human turn that re-enters the run — rendered, refused, and honest about which.
 *
 * This is the point of the Solution Workflow screen. `M10` built resume-on-review-comment, so the
 * machinery for a reviewer's turn to re-enter a run exists; what does not exist is a route the
 * console can post it to. **Sync's API is read-only**, held behaviourally by
 * `tests/test_api_routes.py::test_no_route_reaches_past_the_read_surface`, and the only write route
 * in the whole surface is `POST /api/repos/{repo_id}/context`.
 *
 * So the screen states the refusal in words. The alternative — a working-looking submit
 * that silently does nothing, or a `POST` invented against a route that would 404 — is the worst
 * outcome available on a screen whose entire argument is that it does not ask to be trusted on
 * faith. A reviewer who types here and is told plainly that nothing is stored has been told the
 * truth; one who types here and watches a spinner has been lied to.
 *
 * The field stays typeable rather than disabled, because a dead textarea says nothing about what
 * the interface will be and a live one lets a reviewer see the shape of the turn they will get.
 *
 * **There is no submit control at all, by the owner's ruling of 2026-08-21.** It was a disabled
 * button naming a route that does not exist, and a button drawn for a capability the product does
 * not have reads as a feature merely switched off — a shape promising that pressing is the only
 * thing missing. The refusal is prose instead, and the field points at it, so the missing capability
 * and the route that would serve it are stated rather than mimed.
 */

import { useId, useState } from "react"

import { MetricPanel } from "@/components/metric-panel"
import { Textarea } from "@/components/ui/textarea"

/** The route a reply needs, named so the gap is a work item rather than a shrug. */
export const REPLY_ROUTE = "POST /api/workflows/{finding_id}/reply"

export interface ReplyBoxProps {
  /**
   * The node the graph still owes a visit, or `null` on a run that reached a terminal outcome.
   *
   * This decides WHICH refusal applies, and the distinction came out of `superlog-02`: their run
   * states carry `awaiting_human`, and a reply in that state resumes the investigation in place
   * rather than starting a new run. A reply box on a waiting run and a reply box on a finished one
   * are two different refusals, and naming only the missing route collapses them into one.
   */
  readonly waitingOn: string | null
}

export function ReplyBox({ waitingOn }: ReplyBoxProps) {
  const fieldId = useId()
  const explanationId = useId()
  const [draft, setDraft] = useState("")

  return (
    <MetricPanel
      label="Reply to this run"
      caption="A reviewer's turn: request changes to the patch, explain what the run got wrong, or add context the graph did not have."
    >
      <div className="flex flex-col gap-row">
        <label htmlFor={fieldId} className="furniture text-meta text-ink-muted">
          Your reply to this run
        </label>
        <Textarea
          id={fieldId}
          value={draft}
          rows={4}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Narrow the patch to the call site, and leave the helper alone."
          aria-describedby={explanationId}
        />
      </div>

      {/* Which refusal applies, before the one about the route. The route is missing either way;
          whether a reply would achieve anything if it existed depends on the run. */}
      <p className="max-w-prose text-body text-ink-muted">
        {waitingOn === null ? (
          <>
            This run <strong>reached a terminal outcome</strong>. Even with the route below, a reply
            would not resume it -- there is no node left for the graph to visit, so a reply would be
            the start of something else, and nothing here decides what that is.
          </>
        ) : (
          <>
            This run <strong>has not finished</strong>: the graph still owes{" "}
            <code className="font-mono">{waitingOn}</code> a visit. This is the state a reply is for
            -- a reviewer's turn that re-enters the run in place rather than starting a second one.
          </>
        )}
      </p>

      <p id={explanationId} className="max-w-prose text-body text-ink-muted">
        This cannot be sent. Sync's API is read-only — no route mutates a run, and the only write
        route on the whole surface is <code className="font-mono">POST /api/repos/{"{repo_id}"}/context</code>.
        Sending a reply into a run needs a route that does not exist yet:{" "}
        <code className="font-mono">{REPLY_ROUTE}</code>. Nothing typed here is stored, queued or
        sent, and the refusal is stated here rather than mimed by a control that cannot act, so the
        gap reads as a work item instead of a feature nobody thought of.
      </p>
    </MetricPanel>
  )
}
