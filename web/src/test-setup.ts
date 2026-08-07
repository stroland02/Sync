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
