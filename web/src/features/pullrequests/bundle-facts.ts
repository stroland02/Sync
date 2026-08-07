/**
 * The three facts the rail states, lifted out of evidence the transport does not type.
 *
 * `WorkflowState` carries no pull request number, no address and no branch. Each is a key inside
 * `nodes[].evidence`, which is `Record<string, unknown>` — so the payload promises nothing about
 * whether the key is there, what type it holds, or whether the node carrying it exists at all. That
 * makes reading three of them a derivation with several wrong answers available, which is why it is
 * a module with a test rather than three expressions inside a component.
 *
 * The two absence phrases are here for the same reason. A pull request missing because routing
 * decided against a patch, missing because the run was abandoned before it got there, and missing
 * because the run has not got there yet are three different facts, and one sentence for all three is
 * the "nearly right label" defect this milestone keeps finding. They are the short form on purpose:
 * the long form of each is already on the same screen once, in `Framing` and in the outcome panel,
 * and both earlier detail ports found the same defect on their 404 walk — a rail repeating a panel's
 * whole sentence per row is one fact written five times.
 */

import type { WorkflowNode, WorkflowOutcome } from "@/api/types"

export interface BundleFacts {
  /** `open_pr`'s `pr_number`, as a string. */
  prNumber: string | null
  /** `open_pr`'s `pr_url`, http and https only. Anything else is not a destination. */
  prUrl: string | null
  /** `push_branch`'s `branch`. */
  branch: string | null
}

/** A scalar as a string. An object or an array is not a scalar and is an absence, not `[object Object]`. */
function asScalarText(value: unknown): string | null {
  if (typeof value === "string") return value === "" ? null : value
  if (typeof value === "number" || typeof value === "boolean") return String(value)
  return null
}

/**
 * A URL the payload gave, or null.
 *
 * The value originates in the customer's repository by way of the forge, which makes it untrusted
 * input arriving at a boundary. Anything that is not http or https is not rendered as an anchor: a
 * `javascript:` href is a script the console would run on somebody else's say-so. Nothing here
 * constructs a URL the payload did not send.
 *
 * This is the same rule `features/workflows/evidence.tsx` applies to the same value, and the two
 * copies are B125's second half — that file's `asHttpUrl` is not exported and M7-W180 did not open
 * another level's directory to export it.
 */
function asHttpUrl(value: unknown): string | null {
  if (typeof value !== "string" || value === "") return null
  let parsed: URL
  try {
    parsed = new URL(value)
  } catch {
    return null
  }
  return parsed.protocol === "http:" || parsed.protocol === "https:" ? value : null
}

function evidenceOf(nodes: WorkflowNode[], name: string): Record<string, unknown> {
  return nodes.find((node) => node.name === name)?.evidence ?? {}
}

export function bundleFacts(nodes: WorkflowNode[]): BundleFacts {
  const openPr = evidenceOf(nodes, "open_pr")
  const pushBranch = evidenceOf(nodes, "push_branch")
  return {
    prNumber: asScalarText(openPr.pr_number),
    prUrl: asHttpUrl(openPr.pr_url),
    branch: asScalarText(pushBranch.branch),
  }
}

/** Which nothing the rail's Pull request row is. `null` and `running` are one state, not two. */
export function noPullRequestPhrase(outcome: WorkflowOutcome | null): string {
  if (outcome === null || outcome === "running") return "the run has not opened one yet"
  if (outcome === "reported") return "no patch was warranted, so none was opened"
  if (outcome === "abandoned") return "the run was abandoned before one was opened"
  if (outcome === "opened") return "the run opened one and recorded no number"
  // Named rather than folded into whichever branch fell through last, which is the rule
  // `features/workflows/run-outcome.tsx` states at its own final branch: an unknown outcome
  // rendered as a known one is a confident wrong verdict.
  return "an outcome this console has not caught up with, so it cannot say"
}

/** Which nothing the rail's Branch row is. A missing branch is not a missing pull request. */
export function noBranchPhrase(outcome: WorkflowOutcome | null): string {
  if (outcome === null || outcome === "running") return "the run has not pushed anything yet"
  if (outcome === "reported") return "no patch was attempted, so nothing was pushed"
  if (outcome === "abandoned") return "the run was abandoned before it pushed"
  if (outcome === "opened") return "the run opened a pull request and recorded no branch"
  return "an outcome this console has not caught up with, so it cannot say what was pushed"
}
