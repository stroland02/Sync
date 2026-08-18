/**
 * The human turn that re-enters the run — rendered, refused, and honest about which.
 *
 * This is the point of the Solution Workflow screen. `M10` built resume-on-review-comment, so the
 * machinery for a reviewer's turn to re-enter a run exists; what does not exist is a route the
 * console can post it to. **Sync's API is read-only**, held behaviourally by
 * `tests/test_api_routes.py::test_no_route_reaches_past_the_read_surface`, and the only write route
 * in the whole surface is `POST /api/repos/{repo_id}/context`.
 *
 * So the control renders and states its own refusal. The alternative — a working-looking submit
 * that silently does nothing, or a `POST` invented against a route that would 404 — is the worst
 * outcome available on a screen whose entire argument is that it does not ask to be trusted on
 * faith. A reviewer who types here and is told plainly that nothing is stored has been told the
 * truth; one who types here and watches a spinner has been lied to.
 *
 * The field stays typeable rather than disabled, because a dead textarea says nothing about what
 * the interface will be and a live one lets a reviewer see the shape of the turn they will get.
 * The submit control is the thing that must not lie, and it is the thing that is off.
 */

import { useId, useState } from "react"

import { MetricPanel } from "@/components/metric-panel"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"

/** The route a reply needs, named so the gap is a work item rather than a shrug. */
export const REPLY_ROUTE = "POST /api/workflows/{finding_id}/reply"

export function ReplyBox() {
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
        />
      </div>

      <p id={explanationId} className="max-w-prose text-body text-ink-muted">
        This cannot be sent. Sync's API is read-only — no route mutates a run, and the only write
        route on the whole surface is <code className="font-mono">POST /api/repos/{"{repo_id}"}/context</code>.
        Sending a reply into a run needs a route that does not exist yet:{" "}
        <code className="font-mono">{REPLY_ROUTE}</code>. Nothing typed here is stored, queued or
        sent, and the control is shown rather than omitted so the gap is visible instead of looking
        like a feature nobody thought of.
      </p>

      <div>
        <Button variant="outline" size="sm" disabled aria-describedby={explanationId}>
          Send reply
        </Button>
      </div>
    </MetricPanel>
  )
}
