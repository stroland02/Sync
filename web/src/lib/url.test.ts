import { describe, expect, it } from "vitest"

import { asHttpUrl } from "@/lib/url"

describe("asHttpUrl", () => {
  it("accepts valid https and http URLs", () => {
    expect(asHttpUrl("https://github.com/org/repo/pull/1")).toBe(
      "https://github.com/org/repo/pull/1",
    )
    expect(asHttpUrl("http://localhost:8080/path")).toBe("http://localhost:8080/path")
  })

  it("rejects non-http protocols like javascript: and data:", () => {
    expect(asHttpUrl("javascript:alert(1)")).toBeNull()
    expect(asHttpUrl("data:text/html,hello")).toBeNull()
    expect(asHttpUrl("ftp://example.com")).toBeNull()
  })

  it("rejects malformed URLs, empty strings, and non-strings", () => {
    expect(asHttpUrl("not-a-url")).toBeNull()
    expect(asHttpUrl("")).toBeNull()
    expect(asHttpUrl(null)).toBeNull()
    expect(asHttpUrl(undefined)).toBeNull()
    expect(asHttpUrl(42)).toBeNull()
    expect(asHttpUrl({})).toBeNull()
  })
})
