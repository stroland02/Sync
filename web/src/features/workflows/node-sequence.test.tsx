/**
 * The one animation left in the console that tracks a state change, and the gate that makes that
 * sentence true rather than aspirational.
 *
 * `DESIGN.md`'s Motion section permits motion where the data holds a time. A node's status changing
 * under a poll is such a time: the checkpointer wrote a checkpoint at a moment, and the wash says
 * *this just happened*. A re-render is not such a time, and neither is a mount — the workflow page
 * polls every five seconds, so a wash that fired on arrival or on an unchanged refetch would claim a
 * checkpoint had just been written every time an operator opened the screen or left it open. That is
 * a false claim about when, which is the specific failure motion is capable of.
 *
 * So the gate — not the animation — is what is tested here. `ChangeWash` is private to
 * `node-sequence.tsx`, and the observable it is asserted through is what a reader can actually see:
 * whether a wash element exists in the rendered node marker. It is `aria-hidden` and carries no
 * text, so it is queried structurally rather than by role.
 *
 * Written for M4.5-W143 and shown red before being trusted, and **what the attempt found is worth
 * more than the guard**. Four deliberate breaks against the real component:
 *
 * - Removing the `changeCount === 0` early return reddens the first two (`expected 1 to be +0`).
 * - Stopping the increment reddens the last two (`expected +0 to be 1`).
 * - Removing `ChangeWash`'s mount guard changes nothing. All four still pass.
 * - Removing its `previous.current !== status` comparison changes nothing either.
 *
 * The last two are the finding. `previous` is seeded with `useRef(status)`, so the comparison is
 * already equal on the first effect run, and the effect's dependency array is `[status]`, so it does
 * not run at all on an unchanged refetch. Both guards are therefore unreachable — defensive code for
 * conditions the hook's own shape prevents. M4.5-W143 measured that and deliberately did not delete
 * them: the trigger is a live poll this session could not exercise against the graph, and an
 * unverifiable simplification to the one animation left in the console is a worse trade than a
 * redundancy that is written down. **So this comment is the record, not a claim that they matter.**
 *
 * What these four do bind is the observable an operator sees: a wash exists only after a status
 * transition, exactly one at a time, never on arrival and never on a poll that changed nothing.
 * That is the property `DESIGN.md` licenses the animation for, and it holds however the internals
 * are later simplified.
 */

import { cleanup, render } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import type { WorkflowNode } from "@/api/types"
import { NodeSequence } from "@/features/workflows/node-sequence"

afterEach(cleanup)

function node(over: Partial<WorkflowNode> = {}): WorkflowNode {
  return {
    name: "patch",
    status: "current",
    standing: "due",
    evidence: {},
    ...over,
  }
}

/**
 * The wash is the absolutely-positioned overlay inside the node's marker. Selecting on the marker's
 * own children rather than on a test id keeps this a structural assertion about what renders, which
 * is the only kind this suite is allowed to make about appearance.
 */
function washCount(container: HTMLElement): number {
  return container.querySelectorAll("span.absolute").length
}

describe("the node-status wash", () => {
  it("washes nothing on mount, because arriving at a screen is not a checkpoint", () => {
    const { container } = render(<NodeSequence nodes={[node({ status: "current" })]} />)

    expect(washCount(container)).toBe(0)
  })

  it("washes nothing when a poll returns the same status", () => {
    const { container, rerender } = render(<NodeSequence nodes={[node({ status: "current" })]} />)

    rerender(<NodeSequence nodes={[node({ status: "current" })]} />)
    rerender(<NodeSequence nodes={[node({ status: "current" })]} />)

    expect(washCount(container)).toBe(0)
  })

  it("washes when the status actually changes, which is the checkpoint it claims", () => {
    const { container, rerender } = render(<NodeSequence nodes={[node({ status: "current" })]} />)

    rerender(<NodeSequence nodes={[node({ status: "done", standing: "ran" })]} />)

    expect(washCount(container)).toBe(1)
  })

  it("does not accumulate washes across several changes", () => {
    // One wash element at a time, keyed on the change count so a second transition replaces the
    // first rather than stacking a second overlay on the same marker. Two overlays fading together
    // would render a darker wash for a node that changed twice, which is a claim about magnitude
    // that no checkpoint carries.
    const { container, rerender } = render(<NodeSequence nodes={[node({ status: "current" })]} />)

    rerender(<NodeSequence nodes={[node({ status: "done", standing: "ran" })]} />)
    rerender(<NodeSequence nodes={[node({ status: "current", standing: "due_again" })]} />)

    expect(washCount(container)).toBe(1)
  })
})
