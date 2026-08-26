/**
 * The run stream, and the four guards it inherited from the card it replaced.
 *
 * **Ported from `features/fleet/runs-table.test.tsx`, which was deleted with its subject.** The
 * concerns are unchanged and the subject is not: `RunsCard` owned a `useRuns` call and a filter
 * rail, so every case here had to stand up a `vi.mock("@/api/queries")` harness to reach a table.
 * `RunsStream` takes the page as a prop, so the harness is gone and the tests got simpler rather
 * than weaker. Two of the four — rehearsal labelling and the unlinked finding — would otherwise
 * have gone on passing against a deleted file.
 *
 * One guard did change subject on purpose. The old table linked the Finding cell to the workflow;
 * the stream keeps one line per row and the link moved into the run record drawer, so the
 * workspace-scoped-address guard moved with it to `runs-page.test.tsx`. What stays here is that
 * the stream still names the finding either way.
 *
 * Scope is `console-dev-loop.md`'s: classification, derivation and structural invariants, never
 * class names and never a snapshot.
 */

import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import type { RunRow, RunsPage } from "@/api/types"
import { RunsStream } from "@/features/runs/runs-stream"

afterEach(cleanup)

function run(overrides: Partial<RunRow> = {}): RunRow {
  return {
    thread_id: "finding-1:prod-run-1:0",
    finding_id: "finding-1",
    finding_name: null,
    liveness: null,
    last_heartbeat_at: null,
    repo_id: "org/one",
    run_id: "prod-run-1",
    current_node: null,
    outcome: "opened",
    abandon_reason: null,
    last_checkpoint_at: "2026-08-05T12:00:00Z",
    ...overrides,
  }
}

function page(items: RunRow[], overrides: Partial<RunsPage> = {}): RunsPage {
  return {
    items,
    total: items.length,
    next_offset: null,
    // `sync.dashboard.fleet.runs` always returns these, computed before the outcome filter
    // applies -- which is what lets the chips' counts say what each selection would return.
    by_disposition: {},
    unfiltered_total: items.length,
    ...overrides,
  }
}

function renderStream(data: RunsPage, narrowed = false) {
  return render(
    <RunsStream page={data} selected={null} onSelect={() => {}} narrowed={narrowed} />,
  )
}

describe("the run stream", () => {
  it("labels rehearsal runs distinctly from live runs", () => {
    renderStream(
      page([
        run({ thread_id: "finding-live-1:prod-run-1:0", run_id: "prod-run-1" }),
        run({
          thread_id: "finding-rehearse-1:rehearsal-2026-08-05:0",
          finding_id: "finding-rehearse-1",
          run_id: "rehearsal-2026-08-05",
          outcome: "reported",
        }),
      ]),
    )

    expect(screen.getByText("live")).toBeTruthy()
    expect(screen.getByText("rehearsal")).toBeTruthy()
    expect(screen.getByText("halted before the remote")).toBeTruthy()
  })

  it("keeps its column headers when there is nothing to list", () => {
    renderStream(page([]))

    // Decision 61: the shape of the data is legible before there is data, so a reader learns what
    // a run IS from a screen that has none. Swapping the whole table for a paragraph takes that
    // away exactly when it is most useful.
    expect(screen.getByRole("columnheader", { name: /outcome/i })).not.toBeNull()
    expect(screen.getByText(/No run has ever checkpointed/)).not.toBeNull()
  })

  it("keeps the two nothings apart when a narrowing matched no run", () => {
    // The assertion that catches a tidy-up merging them. "Nothing carries this disposition" and
    // "nothing has ever run" are different answers, and only one of them is about the chip the
    // reader pressed.
    renderStream(page([], { total: 0, unfiltered_total: 31 }), true)

    expect(screen.getByText(/No run matches this narrowing/)).not.toBeNull()
    expect(screen.queryByText(/No run has ever checkpointed/)).toBeNull()
    expect(screen.getByText(/31 runs/)).not.toBeNull()
  })

  it("names the finding when the graph no longer holds it, rather than leaving a gap", () => {
    // `finding_name` is null for a run whose finding a scan rebuilt away. The checkpointer
    // outlives `finding`, so this is the normal state of an old run and not a data defect.
    renderStream(page([run({ finding_name: null })]))

    expect(screen.getByText(/no longer in the graph/)).not.toBeNull()
  })

  it("puts something in the Record column on every row, including the rows with nothing to say", () => {
    // The reference fills a message cell on every row and our runs carry no message field. An
    // empty cell would render "we recorded nothing" as "nothing happened".
    renderStream(page([run({ outcome: "opened", abandon_reason: null, current_node: null })]))

    expect(screen.getByText(/nothing recorded beyond the outcome/)).not.toBeNull()
  })

  it("marks the open run without removing it from the stream", () => {
    // A drawer is not a navigation: the row stays where it was, and the address and the screen
    // agree about which one is open.
    render(
      <RunsStream
        page={page([run({ thread_id: "finding-1:prod-run-1:0" })])}
        selected="finding-1:prod-run-1:0"
        onSelect={() => {}}
        narrowed={false}
      />,
    )

    const rows = screen.getAllByRole("row")
    const selected = rows.filter((row) => row.getAttribute("aria-selected") === "true")
    expect(selected).toHaveLength(1)
  })
})
