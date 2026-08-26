/**
 * The derivations the Solutions board carries weight on.
 *
 * **Rewritten 2026-08-26 (`CI-W647`), when the owner ruled this screen a board rather than a
 * table.** Both subjects it covered left with the panels they belonged to, and every assertion they
 * carried has a successor here rather than a deletion. `dispositionRows` turned `by_disposition`
 * into ranked bars and the column headings are now that same payload — including the one inversion
 * the ruling forces: a disposition with no run was *absent* from the bars and must be *present with
 * a zero* as a column. `SolutionsFunnelRegion` proved three nothings did not render as one blank,
 * and a column has three of its own.
 */

import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it } from "vitest"

import type { RunRow } from "@/api/types"
import { DISPOSITION_OPTIONS } from "@/features/runs/run-row"
import {
  BOARD_STAGES,
  boardColumns,
  groupByDisposition,
  IN_FLIGHT_BUCKET,
  SolutionBoard,
} from "@/features/workflows/solutions-board"

afterEach(cleanup)

function run(overrides: Partial<RunRow> & { thread_id: string }): RunRow {
  return {
    finding_id: "f-1",
    finding_name: "stripe-charges-4b1c9e",
    liveness: null,
    last_heartbeat_at: null,
    repo_id: "demo",
    current_node: null,
    outcome: "opened",
    abandon_reason: null,
    last_checkpoint_at: "2026-08-26T10:00:00Z",
    ...overrides,
  }
}

function renderBoard(props: {
  byDisposition: Record<string, number>
  items: RunRow[]
  unfilteredTotal: number
}) {
  const { columns } = boardColumns(props.byDisposition)
  const { container } = render(
    <MemoryRouter>
      <SolutionBoard
        columns={columns}
        items={props.items}
        unfilteredTotal={props.unfilteredTotal}
        repoId="demo"
        selected={null}
        onSelect={() => {}}
      />
    </MemoryRouter>,
  )
  return container
}

describe("boardColumns", () => {
  /**
   * The closed-set rule, and the only assertion here that would catch the board inventing a stage.
   *
   * The owner's ruling is that the vocabulary comes from what the payload already carries.
   * `DISPOSITION_OPTIONS` is that vocabulary — the chips on Runs offer it and `sync.dashboard`
   * writes it — so the board's columns are checked against it rather than against a list retyped
   * in this file, which would agree with itself and with nothing else.
   */
  it("draws one column per member of the payload's own vocabulary, and no others", () => {
    const buckets = BOARD_STAGES.map((stage) => stage.bucket)
    const filters = BOARD_STAGES.map((stage) => stage.filter)

    expect(new Set(buckets)).toEqual(new Set(DISPOSITION_OPTIONS.map((o) => o.bucket)))
    expect(new Set(filters)).toEqual(new Set(DISPOSITION_OPTIONS.map((o) => o.value)))
    expect(buckets.length).toBe(DISPOSITION_OPTIONS.length)
  })

  /**
   * The owner's inversion, stated as a test. `dispositionRows` returned `[]` for a payload that
   * counted nothing, which was right for a ranking and wrong for a board: an absent column says
   * the stage does not exist.
   */
  it("renders every column with a zero when the payload counted nothing", () => {
    const { columns } = boardColumns({})

    expect(columns.length).toBe(BOARD_STAGES.length)
    expect(columns.every((column) => column.count === 0)).toBe(true)
  })

  /** The bucket the board exists to name: a run still going is not a run in a column called "null". */
  it("gives the in-flight bucket a column whose heading is not the string null", () => {
    const { columns } = boardColumns({ [IN_FLIGHT_BUCKET]: 3 })
    const inFlight = columns.find((column) => column.stage.bucket === IN_FLIGHT_BUCKET)

    expect(inFlight?.count).toBe(3)
    expect(inFlight?.stage.label).not.toBe("null")
    expect(inFlight?.stage.label.toLowerCase()).toContain("flight")
  })

  /**
   * A count with no column is the board's own way of losing runs, and it is the successor to
   * `dispositionRows` keeping an unrecognised disposition rather than dropping it. The transport
   * should never emit one — it folds an unknown outcome into the in-flight bucket — so this is the
   * guard for the day that stops being true.
   */
  it("hands back a disposition it has no column for rather than dropping it", () => {
    const { columns, unrecognised } = boardColumns({ opened: 1, quarantined: 2 })

    expect(columns.map((column) => column.stage.bucket)).not.toContain("quarantined")
    expect(unrecognised).toEqual([{ key: "quarantined", count: 2 }])
  })
})

describe("groupByDisposition", () => {
  it("files a run with no outcome under the same bucket its heading is counted from", () => {
    const grouped = groupByDisposition([run({ thread_id: "a", outcome: null })])

    expect(grouped[IN_FLIGHT_BUCKET]?.map((r) => r.thread_id)).toEqual(["a"])
  })

  it("keeps each column in the order the payload sent, which is newest first", () => {
    const grouped = groupByDisposition([
      run({ thread_id: "new", outcome: "abandoned" }),
      run({ thread_id: "old", outcome: "abandoned" }),
    ])

    expect(grouped.abandoned?.map((r) => r.thread_id)).toEqual(["new", "old"])
  })
})

describe("an empty column", () => {
  /**
   * The successor to the funnel's three-nothings test, and it fails the same way: a column that
   * renders every empty state as one blank tells a reader nothing about which nothing it is.
   */
  it("says which of its three nothings it is, in three different non-empty sentences", () => {
    const nothingEver = renderBoard({
      byDisposition: {},
      items: [],
      unfilteredTotal: 0,
    }).textContent
    cleanup()
    const emptyStage = renderBoard({
      byDisposition: { opened: 4 },
      items: [run({ thread_id: "a" })],
      unfilteredTotal: 4,
    }).textContent
    cleanup()
    const notInWindow = renderBoard({
      byDisposition: { opened: 1, abandoned: 40 },
      items: [run({ thread_id: "a" })],
      unfilteredTotal: 41,
    }).textContent

    for (const text of [nothingEver, emptyStage, notInWindow]) {
      expect(text?.trim()).not.toBe("")
    }
    expect(new Set([nothingEver, emptyStage, notInWindow]).size).toBe(3)
  })

  it("distinguishes a stage nothing reached from a checkpointer that holds nothing at all", () => {
    renderBoard({ byDisposition: { opened: 4 }, items: [run({ thread_id: "a" })], unfilteredTotal: 4 })

    // Four of the five stages are empty in this fixture and each says so in its own column, so
    // this is deliberately an "all" query: one match would mean four columns went silent.
    expect(screen.getAllByText(/no run has reached this stage/)).toHaveLength(BOARD_STAGES.length - 1)
  })

  it("says a stage with runs none of which are in this window is not an empty stage", () => {
    renderBoard({
      byDisposition: { opened: 1, abandoned: 40 },
      items: [run({ thread_id: "a" })],
      unfilteredTotal: 41,
    })

    expect(screen.getByText(/none of them in this window of 1/)).toBeTruthy()
  })
})

describe("the board", () => {
  /** A card is a run, and the run a reader needs to say out loud is the finding behind it. */
  it("leads each card with the finding's name and keeps its id beside it", () => {
    renderBoard({
      byDisposition: { opened: 1 },
      items: [run({ thread_id: "a", finding_name: "stripe-charges-4b1c9e", finding_id: "f-9" })],
      unfilteredTotal: 1,
    })

    expect(screen.getByText("stripe-charges-4b1c9e")).toBeTruthy()
    expect(screen.getByText("f-9")).toBeTruthy()
  })

  /** The run whose finding the graph no longer holds is the reason the board is not narrowed. */
  it("names the absence rather than blanking the card when the graph no longer holds the finding", () => {
    renderBoard({
      byDisposition: { opened: 1 },
      items: [run({ thread_id: "a", finding_name: null })],
      unfilteredTotal: 1,
    })

    expect(screen.getByText(/no longer in the graph/)).toBeTruthy()
  })
})
