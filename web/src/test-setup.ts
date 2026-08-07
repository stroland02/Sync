/**
 * What jsdom does not implement and the vendored components need.
 *
 * `matchMedia` is the whole file. jsdom ships no implementation of it at all — the property is
 * simply absent — and the vendored sidebar's `useIsMobile` hook calls it on mount, so every test
 * that renders the chassis threw `window.matchMedia is not a function` before this existed. That is
 * a gap in the test environment rather than a defect in the component: every browser this console
 * runs in has it.
 *
 * The stub reports no match and registers no listener, which makes `useIsMobile` resolve to the
 * desktop branch. That is the right default and not an arbitrary one: `useIsMobile` reads
 * `window.innerWidth` for its actual answer and uses the query only to learn when to re-read it, and
 * jsdom's window is 1024px wide — above the 768px breakpoint either way. A stub that reported a
 * match would therefore contradict the width the same hook is about to measure.
 */

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
