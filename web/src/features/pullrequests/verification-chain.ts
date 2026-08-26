/**
 * The two checks a patch had to survive, read out of evidence the transport does not type.
 *
 * Owner decision 47 puts this chain **visibly below the diff** — never behind a disclosure, never
 * in a tooltip — because it is the whole difference between Sync and a bot that opens pull
 * requests. A reader who has to click to find out whether anything verified the change is being
 * asked to trust the output on faith, which is the thing this console exists to refuse.
 *
 * **A run parked on the customer's CI says so.** That is the failure this module is written
 * around: `attempt_ci_result` is `null` while the run waits, and treating null as "nothing to
 * report" renders a waiting run identically to one that passed. `waiting` is its own state and it
 * is reached deliberately, not by falling off the end of a chain of ifs.
 *
 * Every state is a recorded value from a closed vocabulary and is **legible without its colour** —
 * `CLAUDE.md` permits exactly that and refuses the traffic light, the green dot and any figure
 * that averages the two checks into one. There is no such figure here: two checks are reported as
 * two checks, and "we could not tell" never collapses onto "it passed".
 *
 * A derivation with a test rather than expressions inside a component, for `bundle-facts.ts`'s
 * reason: `nodes[].evidence` is `Record<string, unknown>`, so the payload promises nothing about
 * whether a key is present, what it holds, or whether the node carrying it exists.
 */

import type { WorkflowNode } from "@/api/types"
import type { TagTone } from "@/components/tag"

/**
 * What a check currently says.
 *
 * `waiting` and `unknown` are different absences and must not be merged: waiting means the run
 * reached the check and the answer has not arrived, unknown means the node produced nothing this
 * console can read. `not_reached` is a third — the run never got here at all.
 */
export type CheckState = "passed" | "failed" | "timed_out" | "waiting" | "not_reached" | "unknown"

export interface Check {
  /** What was checked, in the reader's terms rather than the graph's node name. */
  label: string
  state: CheckState
  /** One sentence saying what the state means for this patch. Never a restatement of the label. */
  detail: string
}

function find(nodes: WorkflowNode[], name: string): WorkflowNode | undefined {
  return nodes.find((node) => node.name === name)
}

function compiled(node: WorkflowNode | undefined): Check {
  const label = "TypeScript compiled"
  if (node === undefined) {
    return {
      label,
      state: "unknown",
      detail: "This run carries no compile step, so nothing here says the patch builds.",
    }
  }
  const ok = node.evidence.verify_ok
  if (ok === true) {
    return { label, state: "passed", detail: "The compiler accepted the patched tree." }
  }
  if (ok === false) {
    return { label, state: "failed", detail: "The compiler rejected the patched tree." }
  }
  if (node.standing === "ran") {
    return {
      label,
      state: "unknown",
      detail: "The compile step ran and recorded no verdict, so this patch has not been shown to build.",
    }
  }
  return {
    label,
    state: "not_reached",
    detail: "The run never reached the compile step.",
  }
}

function customerCi(node: WorkflowNode | undefined): Check {
  const label = "The customer's CI"
  if (node === undefined) {
    return {
      label,
      state: "unknown",
      detail: "This run carries no CI step, so nothing here says the customer's own suite ran.",
    }
  }
  const result = node.evidence.attempt_ci_result
  if (result === "passed") {
    return { label, state: "passed", detail: "The customer's own suite accepted the patch." }
  }
  if (result === "failed") {
    return { label, state: "failed", detail: "The customer's own suite rejected the patch." }
  }
  if (result === "timed_out") {
    return {
      label,
      state: "timed_out",
      detail: "Sync stopped waiting for the customer's CI, so it never gave a verdict.",
    }
  }
  // Null with a run that has reached the node is the parked case, and it is the one this module
  // exists for: a run waiting on somebody else's CI must never read as a run that passed it.
  if (node.standing !== "not_reached_yet" || node.evidence.ci_url !== undefined) {
    return {
      label,
      state: "waiting",
      detail: "This run is waiting on the customer's CI. It has not passed and it has not failed.",
    }
  }
  return { label, state: "not_reached", detail: "The run never reached the customer's CI." }
}

/**
 * The chain, in the order the graph runs it.
 *
 * Two entries, always. A check that did not happen is reported as a check that did not happen
 * rather than omitted — dropping it would leave a shorter chain that looks complete, which is
 * how "we could not check" becomes invisible.
 */
export function verificationChain(nodes: WorkflowNode[]): Check[] {
  return [compiled(find(nodes, "static_verify")), customerCi(find(nodes, "await_ci"))]
}

/**
 * A check's tone, where a check is rendered as a tag rather than as a chain row.
 *
 * **Three neutrals, and they are the point.** A run parked on the customer's CI must not wear the
 * tone of one that passed it, and must not wear a failure's either — `waiting`, `not_reached` and
 * `unknown` are three absences, none of them a verdict. Explicit returns with a neutral default
 * rather than a lookup, so a seventh `CheckState` lands on neutral rather than on whichever branch
 * fell through last.
 */
export function checkTone(state: CheckState): TagTone {
  if (state === "passed") return "good"
  if (state === "failed") return "critical"
  if (state === "timed_out") return "serious"
  return "neutral"
}
