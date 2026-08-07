/**
 * The page header renders the registry's sentence, and renders one heading.
 *
 * Behaviour, not class names. `.claude/rules/console-dev-loop.md` bounds this suite to
 * classification, derivation and structural invariants and forbids asserting on classes — the
 * display step's single-consumer rule is held in Python, where it can read the source text.
 * What is left for here is the part a reader actually depends on: the question appears, and there is
 * exactly one `h1`.
 *
 * The second of those is the one worth a test. `RouteEntry.question` existed for nine routes and
 * rendered on none of them, so the failure mode this component has is not a crash — it is a header
 * that quietly drops the sentence and looks fine. And two `h1`s on a screen is the accessibility
 * half of the two-focal-points problem: a heading list with two level-ones tells a screen reader the
 * page is two documents.
 */

import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { PageHeader } from "@/layouts/page-header"
import { ROUTES } from "@/lib/routes"

afterEach(cleanup)

describe("PageHeader", () => {
  it("renders the question the registry holds for the route", () => {
    const route = ROUTES[0]

    render(<PageHeader title="Fleet" question={route.question} />)

    expect(screen.getByText(route.question)).toBeTruthy()
  })

  it("renders exactly one level-one heading, so the screen is one document", () => {
    render(
      <PageHeader
        title="seed-console-scale-stripe"
        question="What is at risk from this vendor?"
        actions={<button type="button">Re-index</button>}
      />
    )

    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1)
  })

  it("puts the subject in the heading rather than the route's generic label", () => {
    // A route's `label` is "Vendor" and its title is the vendor. Only the page knows the subject,
    // which is why this takes it as a prop instead of looking it up — the same reason `Breadcrumbs`
    // takes its trail.
    render(<PageHeader title="seed-console-scale-stripe" question="What is at risk?" />)

    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("seed-console-scale-stripe")
  })

  it("renders the trail and the action when it is given them, and nothing when it is not", () => {
    const { container } = render(<PageHeader title="Fleet" question="What has Sync been doing?" />)

    expect(container.querySelectorAll("button")).toHaveLength(0)
  })
})
