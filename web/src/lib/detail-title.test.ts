/**
 * What the three detail levels are allowed to put at the display step.
 *
 * The defect this closes was measured: `/findings/9f176dea…` spent the page's only focal point on
 * a 32-character hex identifier, at 46px inside a 360px column, where it wrapped to four lines and
 * made the header 253px tall against 104px on Fleet. An opaque identifier is not a name, and a
 * display step is for a name.
 *
 * So the derivation has one rule and it is testable: **a title is assembled from the parts the
 * payload actually carried, and a part the payload did not carry is stated as an absence rather
 * than dropped, guessed, or filled with the identifier.** Four of the branches below exist only
 * because a part can be missing, and each was written red first.
 */

import { describe, expect, it } from "vitest"

import {
  NO_GENERATION,
  NO_OPERATION,
  NO_VENDOR,
  findingTitle,
  pullRequestTitle,
  runTitle,
} from "@/lib/detail-title"

/** The seeded finding the fidelity report measured. Nothing here may ever render it. */
const HEX_ID = "9f176dea35907f95beb29553e574a037"

describe("findingTitle", () => {
  it("names the call site by its vendor and its operation", () => {
    expect(findingTitle("stripe", "POST /v1/charges")).toEqual({
      name: "stripe · POST /v1/charges",
      absent: null,
    })
  })

  it("states the operation's absence rather than dropping it silently", () => {
    expect(findingTitle("stripe", null)).toEqual({ name: "stripe", absent: NO_OPERATION })
  })

  it("reads an empty operation as the absence it is, not as a part of the name", () => {
    expect(findingTitle("stripe", "")).toEqual({ name: "stripe", absent: NO_OPERATION })
  })

  it("survives a payload with no vendor, and says which part is missing", () => {
    expect(findingTitle("", "POST /v1/charges")).toEqual({
      name: "POST /v1/charges",
      absent: NO_VENDOR,
    })
  })

  it("carries no name at all rather than inventing one when the payload carries neither part", () => {
    expect(findingTitle("", null)).toEqual({ name: null, absent: NO_VENDOR })
  })

  it("cannot render the identifier, because it is never given one", () => {
    const title = findingTitle("stripe", "POST /v1/charges")
    expect(title.name).not.toContain(HEX_ID)
    expect(title.name).not.toMatch(/[0-9a-f]{32}/)
  })
})

describe("runTitle", () => {
  it("names the run by its ordinal among the generations the checkpointer holds", () => {
    expect(runTitle(1)).toEqual({ name: "Run 1", absent: null })
    expect(runTitle(3)).toEqual({ name: "Run 3", absent: null })
  })

  it("states an absence rather than naming a run the payload did not count", () => {
    expect(runTitle(0)).toEqual({ name: null, absent: NO_GENERATION })
  })

  it("renders no thread identifier, which is the rail's job", () => {
    expect(runTitle(2).name).not.toMatch(/[0-9a-f]{32}/)
    expect(runTitle(2).name).not.toContain(":")
  })
})

/**
 * The pull request number here is five digits deliberately.
 *
 * `tests/test_console_design_tokens.py::test_no_colour_literal_outside_index_css` reads `#482` as a
 * three-digit hex colour, because it is one. Three, four, six and eight digits are all colours; five
 * is not. Do not shorten it.
 *
 * **Narrowing that guard to ignore an all-digit `#nnn` was considered and refused.** It cannot be
 * done without losing `#000` and `#000000`, which are all-digit colour literals and the two most
 * likely to be hardcoded. The ambiguity is irreducible at those four lengths — no regex tells a
 * three-digit pull request number from a three-digit colour. It costs nothing to avoid here because
 * the console never writes a real pull request number as a literal: every one of them is
 * interpolated from the payload, so a fixture is the only thing the guard can ever collide with.
 */
const PR_NUMBER = "48201"

/** The two phrases `bundle-facts.ts` owns, which this module is handed rather than restating. */
const NO_PR = "the run was abandoned before one was opened"
const NO_BRANCH = "the run was abandoned before it pushed"

describe("pullRequestTitle", () => {
  it("names the bundle by its number and the branch it was pushed from", () => {
    expect(pullRequestTitle(PR_NUMBER, "sync/fix-post-charges", NO_PR, NO_BRANCH)).toEqual({
      name: "#48201 · sync/fix-post-charges",
      absent: null,
    })
  })

  it("states which nothing the branch is, in the caller's words", () => {
    expect(pullRequestTitle(PR_NUMBER, null, NO_PR, NO_BRANCH)).toEqual({
      name: "#48201",
      absent: NO_BRANCH,
    })
  })

  it("falls back to the branch when there is no number, and says why there is none", () => {
    expect(pullRequestTitle(null, "sync/fix-post-charges", NO_PR, NO_BRANCH)).toEqual({
      name: "sync/fix-post-charges",
      absent: NO_PR,
    })
  })

  it("carries no name when the run pushed nothing and opened nothing", () => {
    expect(pullRequestTitle(null, null, NO_PR, NO_BRANCH)).toEqual({
      name: null,
      absent: NO_PR,
    })
  })

  it("never doubles the hash on a number the evidence already spelled with one", () => {
    expect(pullRequestTitle(`#${PR_NUMBER}`, null, NO_PR, NO_BRANCH).name).toBe("#48201")
  })

  it("reads an empty number and an empty branch as absences", () => {
    expect(pullRequestTitle("", "", NO_PR, NO_BRANCH)).toEqual({ name: null, absent: NO_PR })
  })
})

describe("every title", () => {
  it("says something, whichever parts the payload carried", () => {
    const titles = [
      findingTitle("", null),
      runTitle(0),
      pullRequestTitle(null, null, NO_PR, NO_BRANCH),
      findingTitle("stripe", "POST /v1/charges"),
      runTitle(1),
      pullRequestTitle(PR_NUMBER, "sync/x", NO_PR, NO_BRANCH),
    ]
    for (const title of titles) {
      expect(title.name === null && title.absent === null).toBe(false)
    }
  })
})
