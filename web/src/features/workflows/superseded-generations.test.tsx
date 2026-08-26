import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import type { GenerationSummary } from "@/api/types"
import { SupersededGenerations } from "@/features/workflows/superseded-generations"

describe("SupersededGenerations", () => {
  /**
   * Retitled rather than deleted, and the assertion is inverted on purpose. This used to expect
   * `container.firstChild` to be null. The top bar states a `Generations` figure on every run, so
   * a `1` followed by nothing left a reader unable to tell *there is only one* from *the rest are
   * somewhere this screen does not show*. The coverage it carried — that the current run is never
   * listed as superseding itself — is still here.
   */
  it("accounts for the only generation in a sentence, rather than rendering nothing", () => {
    const generations: GenerationSummary[] = [
      {
        thread_id: "f1:sha:0",
        generation: 0,
        outcome: "opened",
        abandon_reason: null,
        report_reason: null,
      },
    ]

    render(<SupersededGenerations generations={generations} currentThreadId="f1:sha:0" />)

    expect(
      screen.getByText("This is the only generation the checkpointer holds for this finding."),
    ).toBeTruthy()
    expect(screen.queryByText("Run 1")).toBeNull()
  })

  it("renders superseded generations with run number, thread_id, outcome, and abandon_reason", () => {
    const generations: GenerationSummary[] = [
      {
        thread_id: "f1:sha:0",
        generation: 0,
        outcome: "abandoned",
        abandon_reason: "static verification failed after 3 attempts",
        report_reason: null,
      },
      {
        thread_id: "f1:sha:1",
        generation: 1,
        outcome: "opened",
        abandon_reason: null,
        report_reason: null,
      },
    ]

    render(
      <SupersededGenerations generations={generations} currentThreadId="f1:sha:1" />,
    )

    expect(screen.getByText("Superseded generation")).toBeTruthy()
    expect(screen.getByText("Run 1")).toBeTruthy()
    expect(screen.getByText("f1:sha:0")).toBeTruthy()
    expect(screen.getByText("abandoned")).toBeTruthy()
    expect(screen.getByText("— static verification failed after 3 attempts")).toBeTruthy()

    // Current generation should not be in the superseded list
    expect(screen.queryByText("Run 2")).toBeNull()
  })
})
