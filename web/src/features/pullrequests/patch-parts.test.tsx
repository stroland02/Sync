/**
 * Where the patch went, and the distinction that went missing when this module was extracted.
 *
 * `pr_url` sat on the payload while nothing on the finding-detail or pull-request screens rendered
 * it, so a patch that opened a pull request looked exactly like one that never did. These hold the
 * three states apart: opened with a number, opened without one, and never opened at all.
 *
 * The pull-request numbers here are four digits because `test_no_colour_literal_outside_index_css`
 * reads `#101` as a three-digit hex colour. A four-digit number matches neither `#RGB` nor
 * `#RRGGBB`.
 */

import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { PatchTargetList } from "@/features/pullrequests/patch-parts"

afterEach(cleanup)

const target = (over: Partial<{ repo_id: string | null; branch: string | null; pr_url: string | null; pr_number: number | null }>) => ({
  repo_id: "acme/web",
  branch: "sync/bump-stripe",
  pr_url: null,
  pr_number: null,
  ...over,
})

describe("where the patch went", () => {
  it("links the pull request by number when the record holds one", () => {
    render(<PatchTargetList target={target({ pr_url: "https://github.com/acme/web/pull/1017", pr_number: 1017 })} />)

    const link = screen.getByRole("link", { name: "#1017" })
    expect(link.getAttribute("href")).toBe("https://github.com/acme/web/pull/1017")
  })

  it("falls back to the url when a pull request carries no number", () => {
    // A pull request with no number is still a pull request; "#null" would invent one.
    render(<PatchTargetList target={target({ pr_url: "https://example.invalid/pr", pr_number: null })} />)

    expect(screen.getByRole("link", { name: "https://example.invalid/pr" })).toBeTruthy()
  })

  it("says no pull request was opened rather than leaving the row off", () => {
    // The row missing entirely is what this test exists to prevent: it read as "opened one" and
    // "never opened one" being the same screen.
    render(<PatchTargetList target={target({ pr_url: null })} />)

    expect(screen.queryByRole("link")).toBeNull()
    expect(screen.getByText(/opened no pull request/i)).toBeTruthy()
  })

  it("opens the pull request away from the console, and tells the browser not to leak the opener", () => {
    render(<PatchTargetList target={target({ pr_url: "https://github.com/acme/web/pull/7", pr_number: 7 })} />)

    const link = screen.getByRole("link", { name: "#7" })
    expect(link.getAttribute("target")).toBe("_blank")
    expect(link.getAttribute("rel")).toContain("noopener")
  })
})
