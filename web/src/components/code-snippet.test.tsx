/**
 * The window is numbered from its place in the file and the subject line is marked in more
 * than colour — the two derivations a wrong `startLine` or a colour-only mark would break
 * silently, which is why they are the two things held here.
 */

import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { CodeSnippet, absentSnippetReason } from "@/components/code-snippet"

afterEach(cleanup)

describe("CodeSnippet", () => {
  it("numbers lines from where the window sits in its file", () => {
    render(
      <CodeSnippet
        code={"const a = 1\nconst b = 2\nconst c = 3"}
        startLine={40}
        markLine={41}
        label="Call site, src/billing.ts:41"
      />
    )

    const rows = [...document.querySelectorAll("tr")].map((row) => row.getAttribute("data-line"))
    expect(rows).toEqual(["40", "41", "42"])
  })

  it("marks exactly the subject line, and not by colour alone", () => {
    render(
      <CodeSnippet
        code={"one\ntwo\nthree"}
        startLine={10}
        markLine={11}
        label="Call site, a.ts:11"
      />
    )

    const marked = [...document.querySelectorAll("[data-marked]")]
    expect(marked).toHaveLength(1)
    expect(marked[0].getAttribute("data-line")).toBe("11")
    // The marker character is the non-colour channel.
    expect(marked[0].textContent).toContain("▸")
  })

  it("renders an unmarked window when no line is the subject", () => {
    render(<CodeSnippet code={"one\ntwo"} startLine={1} label="Contract, stripe.d.ts" />)

    expect(document.querySelector("[data-marked]")).toBeNull()
    expect(screen.getByRole("figure", { name: "Contract, stripe.d.ts" })).toBeTruthy()
  })
})

describe("the two nothings stay apart", () => {
  it("says policy when source is withheld and capture-gap when it is not", () => {
    // The API's `source_served` is what separates them; one sentence for both would collapse
    // "we will not show you" onto "there is nothing captured yet".
    expect(absentSnippetReason(false)).not.toBe(absentSnippetReason(true))
    expect(absentSnippetReason(false)).toMatch(/does not serve source/i)
    expect(absentSnippetReason(true)).toMatch(/indexed before/i)
  })
})
