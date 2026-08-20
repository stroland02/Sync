// The feed's derivations, out of the panel so they are testable as classification.

import { WORKFLOW_POLL_MS, isRunTerminal } from "@/api/queries"
import type { RunActivityEvent, WorkflowState } from "@/api/types"

/**
 * How often the feed re-asks, or `false` once the run cannot change again — the same
 * `isRunTerminal` rule the page polls by, so the feed and the run stop together.
 */
export function activityPollMs(run: WorkflowState | undefined): number | false {
  return isRunTerminal(run) ? false : WORKFLOW_POLL_MS
}

/** The row's leading word: the tool, `note` for prose, a refusal named with its tool. */
export function activityRowLabel(event: RunActivityEvent): string {
  if (event.kind === "note") return "note"
  const tool = event.tool ?? "tool"
  return event.kind === "refusal" ? `refused: ${tool}` : tool
}
