/**
 * The stream, as the console sees it.
 *
 * Three states have to stay apart and they are what these assert: connected and quiet, connected
 * and arriving, and dropped. Decision 76 requires the drop to be rendered rather than hidden, and
 * it can only be rendered if it is distinguishable from silence -- which is what the server's
 * named heartbeat buys and what this hook has to preserve.
 */

import { act, renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useRepositoryEvents } from "@/features/index-graph/use-repository-events"

class FakeEventSource {
  static last: FakeEventSource | null = null
  readonly url: string
  onerror: (() => void) | null = null
  private handlers = new Map<string, (event: MessageEvent) => void>()
  closed = false

  constructor(url: string) {
    this.url = url
    FakeEventSource.last = this
  }

  addEventListener(kind: string, handler: (event: MessageEvent) => void) {
    this.handlers.set(kind, handler)
  }

  emit(kind: string, payload: unknown) {
    this.handlers.get(kind)?.({ data: JSON.stringify(payload) } as MessageEvent)
  }

  close() {
    this.closed = true
  }
}

beforeEach(() => {
  FakeEventSource.last = null
  vi.stubGlobal("EventSource", FakeEventSource)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("useRepositoryEvents", () => {
  it("subscribes to the repository named in the path, not a query string", () => {
    renderHook(() => useRepositoryEvents("org/payments"))

    expect(FakeEventSource.last?.url).toBe("/api/repositories/org%2Fpayments/events")
  })

  it("counts indexed call sites as they arrive", () => {
    const { result } = renderHook(() => useRepositoryEvents("r1"))

    act(() => {
      FakeEventSource.last?.emit("call_site.indexed", { kind: "call_site.indexed", path: "a.ts" })
      FakeEventSource.last?.emit("call_site.indexed", { kind: "call_site.indexed", path: "b.ts" })
    })

    expect(result.current.indexedCount).toBe(2)
  })

  /**
   * The heartbeat is an SSE comment now, so it never reaches a handler and this hook cannot see
   * it. Asserted from the other side: an unrecognised event moves nothing, which is what stops a
   * future frame type quietly inflating a count.
   */
  it("counts nothing it does not recognise", () => {
    const { result } = renderHook(() => useRepositoryEvents("r1"))

    act(() => {
      FakeEventSource.last?.emit("heartbeat", { kind: "heartbeat" })
    })

    expect(result.current.indexedCount).toBe(0)
    expect(result.current.status).toBe("live")
  })

  it("reports a drop as its own state rather than as silence", () => {
    const { result } = renderHook(() => useRepositoryEvents("r1"))

    act(() => {
      FakeEventSource.last?.onerror?.()
    })

    expect(result.current.status).toBe("dropped")
  })

  /** Freeze and name: what arrived before the drop is kept, not discarded. */
  it("keeps the count it had reached when the stream dropped", () => {
    const { result } = renderHook(() => useRepositoryEvents("r1"))

    act(() => {
      FakeEventSource.last?.emit("call_site.indexed", { kind: "call_site.indexed", path: "a.ts" })
      FakeEventSource.last?.onerror?.()
    })

    expect(result.current.status).toBe("dropped")
    expect(result.current.indexedCount).toBe(1)
  })

  it("closes the connection when the caller goes, so a closed tab releases it", () => {
    const { unmount } = renderHook(() => useRepositoryEvents("r1"))
    const source = FakeEventSource.last

    unmount()

    expect(source?.closed).toBe(true)
  })
})
