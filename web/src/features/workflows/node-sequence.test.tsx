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

import { cleanup, fireEvent, render, screen } from "@testing-library/react"
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

/**
 * The narrative's two bracket entries — what arrived, and how the run ended — and where the second
 * one lands.
 *
 * `narrative-order.test.ts` holds the arithmetic; this holds that the component spends it. The two
 * are separable and were separated on purpose: a correct index rendered at the wrong end of the list
 * is the same defect on screen as a wrong index, and only one of the two files can see it.
 *
 * Position is read off `ol > li` order rather than off a class or a test id, which keeps this a
 * structural assertion about what renders — the only kind this suite makes about appearance.
 */
function entryIndexOf(container: HTMLElement, text: string): number {
  const items = Array.from(container.querySelectorAll("ol > li"))
  return items.findIndex((item) => item.textContent?.includes(text) ?? false)
}

describe("the narrative's bracket entries", () => {
  it("renders neither when the caller passes neither, which is the eight-node sequence", () => {
    const { container } = render(<NodeSequence nodes={[node(), node({ name: "static_verify" })]} />)

    expect(container.querySelectorAll("ol > li")).toHaveLength(2)
  })

  it("opens with the arrival entry, above every node", () => {
    const { container } = render(
      <NodeSequence nodes={[node({ standing: "ran" })]} opening={<p>What arrived</p>} />
    )

    expect(entryIndexOf(container, "What arrived")).toBe(0)
  })

  it("closes an abandoned run where it stopped, above the nodes it never reached", () => {
    const { container } = render(
      <NodeSequence
        nodes={[
          node({ name: "locate", standing: "ran" }),
          node({ name: "static_verify", standing: "ran" }),
          node({ name: "replay", standing: "never_reached" }),
          node({ name: "open_pr", standing: "never_reached" }),
        ]}
        closing={<p>Sync abandoned this run.</p>}
      />
    )

    // Third entry of five: two nodes that ran, then the reason, then the two that never did.
    expect(entryIndexOf(container, "Sync abandoned this run.")).toBe(2)
    expect(entryIndexOf(container, "replay")).toBe(3)
  })

  it("closes a completed run last, because that is where the run stopped", () => {
    const { container } = render(
      <NodeSequence
        nodes={[node({ name: "await_ci", standing: "ran" }), node({ name: "open_pr", standing: "ran" })]}
        closing={<p>This run opened a pull request.</p>}
      />
    )

    expect(entryIndexOf(container, "This run opened a pull request.")).toBe(2)
  })

  it("closes a run that reached nothing first, above the entries it explains", () => {
    const { container } = render(
      <NodeSequence
        nodes={[
          node({ name: "patch", standing: "never_reached" }),
          node({ name: "open_pr", standing: "never_reached" }),
        ]}
        opening={<p>What arrived</p>}
        closing={<p>This run reported rather than patched.</p>}
      />
    )

    expect(entryIndexOf(container, "What arrived")).toBe(0)
    expect(entryIndexOf(container, "This run reported rather than patched.")).toBe(1)
  })

  it("washes nothing for a bracket entry, which is not a node and holds no checkpoint", () => {
    const { container, rerender } = render(
      <NodeSequence nodes={[node({ status: "current" })]} closing={<p>still in flight</p>} />
    )

    rerender(<NodeSequence nodes={[node({ status: "done", standing: "ran" })]} closing={<p>done</p>} />)

    expect(washCount(container)).toBe(1)
  })

  it("renders the checkpoint timestamp when first_seen_at is present", () => {
    const { container } = render(
      <NodeSequence
        nodes={[
          node({
            name: "locate",
            status: "done",
            standing: "ran",
            first_seen_at: "2026-08-08T10:00:00.000000+00:00",
            last_seen_at: "2026-08-08T10:03:00.000000+00:00",
          }),
        ]}
      />
    )

    const timeEl = container.querySelector("time")
    expect(timeEl).not.toBeNull()
    expect(timeEl?.getAttribute("datetime")).toBe("2026-08-08T10:00:00.000000+00:00")
    expect(timeEl?.getAttribute("title")).toContain("Checkpoint window:")
  })

  it("renders no time element when first_seen_at is absent", () => {
    const { container } = render(
      <NodeSequence
        nodes={[
          node({
            name: "await_ci",
            status: "pending",
            standing: "never_reached",
            first_seen_at: null,
            last_seen_at: null,
          }),
        ]}
      />
    )

    const timeEl = container.querySelector("time")
    expect(timeEl).toBeNull()
  })
})

/**
 * The evidence disclosure, Task 11: only the last-reached node opens by default; every earlier
 * node with evidence is a click away rather than either hidden for good or dumped on screen.
 */
describe("the evidence disclosure", () => {
  it("hides a non-default node's evidence until its button is clicked", () => {
    render(
      <NodeSequence
        nodes={[
          node({ name: "locate", standing: "ran", evidence: { tier: "Tier 1" } }),
          node({ name: "patch", standing: "due", evidence: {} }),
        ]}
      />
    )

    // "patch" is the last reached node (due counts as reached) and carries no evidence, so the
    // only button on screen belongs to "locate" — reached, but not last, and closed by default.
    expect(screen.queryByText("Tier 1")).toBeNull()

    const button = screen.getByRole("button", { name: /evidence/i })
    expect(button.getAttribute("aria-expanded")).toBe("false")

    fireEvent.click(button)

    expect(screen.getByText("Tier 1")).not.toBeNull()
    expect(button.getAttribute("aria-expanded")).toBe("true")
  })

  it("opens the last reached node's evidence without a click", () => {
    render(
      <NodeSequence
        nodes={[
          node({ name: "locate", standing: "ran", evidence: {} }),
          node({ name: "static_verify", standing: "ran", evidence: { verify_ok: true } }),
        ]}
      />
    )

    expect(screen.getByText(/PASS/)).not.toBeNull()
  })
})

/**
 * The evidence-age figure, Task 11: staleness, never liveness, and only when there is both an
 * unfinished run and a timestamp to measure it from.
 */
describe("the evidence age", () => {
  it("renders beside the due node when the run is unfinished and something is stamped", () => {
    render(
      <NodeSequence
        nodes={[
          node({
            name: "locate",
            standing: "ran",
            first_seen_at: "2026-08-17T14:00:00.000000+00:00",
            last_seen_at: "2026-08-17T14:00:05.000000+00:00",
          }),
          node({ name: "patch", standing: "due" }),
        ]}
        outcome={null}
      />
    )

    expect(screen.getByText(/since last evidence/i)).not.toBeNull()
  })

  it("renders nothing when nothing has been stamped yet", () => {
    render(
      <NodeSequence
        nodes={[node({ name: "locate", standing: "due", first_seen_at: null, last_seen_at: null })]}
        outcome={null}
      />
    )

    expect(screen.queryByText(/since last evidence/i)).toBeNull()
  })

  it("renders nothing once the run has an outcome, even with a due node and a stamp", () => {
    render(
      <NodeSequence
        nodes={[
          node({
            name: "locate",
            standing: "ran",
            first_seen_at: "2026-08-17T14:00:00.000000+00:00",
            last_seen_at: "2026-08-17T14:00:05.000000+00:00",
          }),
          node({ name: "patch", standing: "due" }),
        ]}
        outcome="opened"
      />
    )

    expect(screen.queryByText(/since last evidence/i)).toBeNull()
  })
})

describe("the node mechanics disclosure", () => {
  /**
   * M13-W227 put this text inside `NodeEvidence` under the title "Reasoning & Strategy", where
   * it read as reasoning the run recorded. It is static -- the same words for every run of that
   * node -- so it was rehomed beside the purpose sentence and retitled. This asserts the part
   * that matters: it is a sibling of the evidence disclosure and never inside it, so opening it
   * cannot be mistaken for opening what the run actually produced.
   */
  it("stays visible while the evidence it sits beside is still collapsed", () => {
    render(
      <NodeSequence
        nodes={[node({ name: "locate", standing: "ran", evidence: { tier: "Tier 1" } })]}
      />
    )

    const toggle = screen.getByRole("button", { name: /evidence/i })
    const panelId = toggle.getAttribute("aria-controls")
    const panel = panelId === null ? null : document.getElementById(panelId)
    const mechanics = screen.getByText("How this node works")

    // The panel holds what this run produced. The mechanics text describes how the node works in
    // general and is true whether or not the run produced anything, so it must sit outside.
    expect(panel).not.toBeNull()
    expect(panel!.contains(mechanics)).toBe(false)
  })

  it("says nothing for a node it does not name, rather than inventing a description", () => {
    render(<NodeSequence nodes={[node({ name: "some_future_node", standing: "ran" })]} />)

    expect(screen.queryByText("How this node works")).toBeNull()
  })
})
