/**
 * What jsdom does not implement and the vendored components need.
 *
 * Two properties, and both are gaps in the test environment rather than defects in a component:
 * every browser this console runs in has each of them.
 *
 * `ResizeObserver` and `scrollIntoView` are what cmdk measures its own list with and how it keeps
 * the selected item on screen, so any test that *opens* a command menu threw before these existed.
 * Nothing had opened one until the top bar's scope switchers put a command menu behind a popover
 * trigger. Both stubs do nothing, which is right rather than merely convenient: jsdom lays nothing
 * out, so a stub that reported a size or a scroll position would be reporting a fiction.
 *
 * `matchMedia` came first. jsdom ships no implementation of it at all — the property is simply
 * absent — and the vendored sidebar's `useIsMobile` hook calls it on mount, so every test that
 * renders the chassis threw `window.matchMedia is not a function`.
 *
 * The stub reports no match and registers no listener, which makes `useIsMobile` resolve to the
 * desktop branch. That is the right default and not an arbitrary one: `useIsMobile` reads
 * `window.innerWidth` for its actual answer and uses the query only to learn when to re-read it, and
 * jsdom's window is 1024px wide — above the 768px breakpoint either way. A stub that reported a
 * match would therefore contradict the width the same hook is about to measure.
 *
 * `EventSource` is the fourth, and it was found by a guard rather than by a crash. jsdom ships no
 * implementation, `useRepositoryEvents` constructs one on mount, and the `ErrorBoundary` above the
 * graph page caught the `ReferenceError` — so the screen rendered its fallback and every assertion
 * about the screen itself was answered by the boundary instead. It never opens a connection and
 * never dispatches, which leaves `useRepositoryEvents` at the optimistic `live` its own first
 * `useState` sets; a test asserting on stream *status* wants a fake it can drive, not this.
 */

if (
  typeof Element !== "undefined" &&
  (Element.prototype as { scrollIntoView?: () => void }).scrollIntoView === undefined
) {
  Element.prototype.scrollIntoView = function scrollIntoView() {}
}

if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

if (typeof globalThis.EventSource === "undefined") {
  globalThis.EventSource = class {
    url: string
    onerror: ((this: EventSource, event: Event) => void) | null = null
    onmessage: ((this: EventSource, event: MessageEvent) => void) | null = null
    onopen: ((this: EventSource, event: Event) => void) | null = null
    readyState = 0
    withCredentials = false
    constructor(url: string | URL) {
      this.url = String(url)
    }
    addEventListener() {}
    removeEventListener() {}
    dispatchEvent() {
      return false
    }
    close() {}
  } as unknown as typeof EventSource
}

if (typeof window !== "undefined" && window.matchMedia === undefined) {
  window.matchMedia = (query: string): MediaQueryList =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList
}
