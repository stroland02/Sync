import { describe, expect, it } from "vitest"

import type { DismissalState } from "@/api/types"
import { rulingWord } from "@/features/findings/human-ruling"

function ruling(over: Partial<DismissalState> = {}): DismissalState {
  return { dismissed: false, reason: null, actor: null, history_count: 0, ...over }
}

describe("rulingWord", () => {
  it("gives no word at all while nothing has answered, rather than the word for 'open'", () => {
    // The one that matters. A cell showing `open` over an unanswered read states that nobody has
    // dismissed this finding, which is a claim the request has not earned — and it is exactly the
    // shape of "absence rendered as a measured zero".
    expect(rulingWord("pending")).toBeNull()
    expect(rulingWord("failed")).toBeNull()
  })

  it("reads a finding dismissed and then restored as open, because that is the standing", () => {
    // `dismissed: false` with a history is a finding somebody set aside and somebody restored. The
    // standing is open; the changes of mind are the history the full rendering carries beneath it,
    // and a third word here would put a judgement in a cell that has room for a state.
    expect(rulingWord(ruling({ history_count: 3 }))).toBe("open")
  })

  it("keeps a dismissal apart from an untouched finding", () => {
    expect(rulingWord(ruling({ dismissed: true, reason: "wont-fix" }))).toBe("dismissed")
    expect(rulingWord(ruling())).toBe("open")
  })
})
