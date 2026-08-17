import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { NodeEvidence } from "@/features/workflows/evidence"

afterEach(cleanup)

describe("NodeEvidence", () => {
  it("renders scalars, flags, and blocks for known node fields", () => {
    render(
      <NodeEvidence
        name="static_verify"
        evidence={{
          verify_ok: true,
          diagnostics: "Found 0 errors in 1.2s.",
        }}
      />
    )

    expect(screen.getByText(/PASS — the tree a push would carry compiles/i)).not.toBeNull()
    expect(screen.getByText("Found 0 errors in 1.2s.")).not.toBeNull()
    expect(screen.getByText("DIAGNOSTICS")).not.toBeNull()
  })

  it("renders nothing when evidence is empty", () => {
    const { container } = render(<NodeEvidence name="patch" evidence={{}} />)
    expect(container.firstChild).toBeNull()
  })

  it("renders reasoning and strategy disclosure when node has structured reasoning", () => {
    render(
      <NodeEvidence
        name="locate"
        evidence={{
          tier: "Tier 1",
          routing_row: "stripe.v1.charges.create -> payment_intents",
        }}
      />
    )

    expect(screen.getByText("Reasoning & Strategy")).not.toBeNull()
    expect(screen.getByText(/Decision table evaluates breaking changes/i)).not.toBeNull()
  })

  it("renders unnamed fields gracefully without crashing", () => {
    render(
      <NodeEvidence
        name="custom_node"
        evidence={{
          custom_metric: 42,
        }}
      />
    )

    expect(screen.getByText("custom_metric")).not.toBeNull()
    expect(screen.getByText("42")).not.toBeNull()
  })
})
