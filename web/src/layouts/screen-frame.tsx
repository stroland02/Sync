/**
 * The four bands every screen renders through: identity, controls, content, status.
 *
 * **The bands are a reading order across four elements, not one DOM parent.** Identity is the
 * chassis banner and status is a `<footer>` beside `<main>`, because `app-frame.test.tsx` pins
 * `banner.parentElement` to be the element that also holds `main` — the sidebar must stay outside
 * that column. So a screen cannot render its own status inline; it publishes into the chassis
 * footer through the portal below.
 */

import { createContext, useContext, useEffect, useState, type ReactNode } from "react"
import { createPortal } from "react-dom"
import { useInRouterContext, useLocation } from "react-router"

import { labelFor } from "@/layouts/scope-switchers"

import { StatusBand, type StatusSegment } from "@/layouts/status-band"

const StatusTargetContext = createContext<HTMLElement | null>(null)
const StatusPublishContext = createContext<((segments: StatusSegment[] | null) => void) | null>(null)

/**
 * Held in state behind a callback ref rather than in a `useRef`.
 *
 * Refs attach bottom-up, and `main`'s subtree commits before its later sibling — so a ref read
 * during `ScreenFrame`'s first render is `null` and the status band never mounts. State costs one
 * extra render on mount and none on navigation.
 */
export function useStatusTarget() {
  const [target, setTarget] = useState<HTMLElement | null>(null)
  return { target, footerRef: setTarget }
}

export function StatusTargetProvider({
  target,
  children,
}: {
  target: HTMLElement | null
  children: ReactNode
}) {
  const [published, setPublished] = useState<StatusSegment[] | null>(null)

  return (
    <StatusTargetContext.Provider value={target}>
      <StatusPublishContext.Provider value={setPublished}>
        {children}
        {/* A descendant's published status wins over the screen's own prop: only Settings needs
            this, and it needs it because nine panels each fetch a different countable set. */}
        {target && published ? createPortal(<StatusBand segments={published} />, target) : null}
      </StatusPublishContext.Provider>
    </StatusTargetContext.Provider>
  )
}

/** For a descendant that owns the count its page cannot re-derive. Settings' nine panels. */
export function useScreenStatus(segments: StatusSegment[] | null) {
  const publish = useContext(StatusPublishContext)
  useEffect(() => {
    publish?.(segments)
    return () => publish?.(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(segments?.map((s) => ({ ...s, paging: undefined })))])
}

export function ScreenFrame({
  controls,
  title,
  subtitle,
  status,
  layout = "flow",
  children,
}: {
  /** Omitted entirely when a screen has nothing to narrow — no element, no rule, no reserved
      height. A bar rendered to say "there is nothing here" is chrome asserting an absence
      nobody asked about. */
  controls?: ReactNode
  /** The page's own heading, when the registry's label is not the right words for it. Omitted
      almost always: the title is read from the route registry, so it cannot drift from the nav
      or the trail the way twelve per-page copies did. */
  title?: string
  /** One line under the title saying what the screen answers. Optional, because a screen whose
      title says it needs no second sentence. */
  subtitle?: ReactNode
  /** Required. A screen with nothing to count publishes `{ kind: "none" }` and says why. */
  status: StatusSegment[]
  /** For the two canvases, which computed their own height from the old chassis and would be
      wrong on day one of this one. */
  /**
   * How this screen occupies the locked chassis.
   *
   * `flow` — the default and what nineteen screens do: the content column grows and `main`
   * scrolls it. `fill` — the two canvases, which take their height from the column rather than
   * computing it. `locked` — the screen owns every scrollbar on the page: it stamps
   * `data-screen="locked"`, which is what flips `main` to `overflow-hidden` through `:has()`,
   * and from there each of its panes scrolls its own body.
   */
  layout?: "flow" | "fill" | "locked"
  children: ReactNode
}) {
  // `useLocation` throws outside a router, and this frame is deliberately rendered without one --
  // its own tests do it, and the status fallback below exists for exactly that case. The lookup
  // lives in a child component so the hook stays unconditional; a ternary around `useLocation`
  // reads fine and breaks the rules of hooks.
  const routed = useInRouterContext()
  const target = useContext(StatusTargetContext)
  const publish = useContext(StatusPublishContext)

  // A screen's own status is published through the same channel a panel would use, so the two
  // cannot both mount a band.
  useEffect(() => {
    publish?.(status)
    return () => publish?.(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(status.map((s) => ({ ...s, paging: undefined })))])

  return (
    <>
      {/* No horizontal padding on either band: the chassis column already applies `p-frame`
          (app-frame.tsx:597-601), and repeating it here indents every migrated screen twice. */}
      {/* Above the controls, because a screen says what it is before it offers ways to narrow
          itself -- which is the order every Stitch screen draws and the order the four bands
          describe: identity, then controls, then content. */}
      {title ? (
        <ScreenHeading heading={title} subtitle={subtitle} />
      ) : routed ? (
        <RegistryHeading subtitle={subtitle} />
      ) : null}
      {controls ? (
        <div
          data-band="controls"
          // `shrink-0` for the identity header's reason: under a locked layout the content band
          // claims `flex-1`, and a filled child squeezes whichever siblings can be squeezed.
          className="sticky top-12 z-10 flex shrink-0 flex-wrap items-center gap-section border-b border-line bg-background py-field"
        >
          {controls}
        </div>
      ) : null}
      <div
        data-band="content"
        data-screen={layout === "flow" ? undefined : layout}
        className={
          layout === "flow" ? "flex flex-col gap-8" : "flex min-h-0 flex-1 flex-col gap-8"
        }
      >
        {/* The page names itself here, at the top of its own content, which is where the design
            system's Identity band puts it. Read from the route registry rather than typed per
            screen -- twelve per-page copies is what drifted last time, and the registry is the
            one place the nav, the trail and this heading can all agree.

            It carries `text-page` because it had been rendering at `text-body`: an `h1` at 13px
            above `h2` sections at 18px, a hierarchy inverted, measured on the Findings screen. */}
        {children}
      </div>
      {/* Fallback for a tree with no provider — tests that render a screen in isolation. */}
      {!target && !publish ? <StatusBand segments={status} /> : null}
    </>
  )
}

/** The page's own heading and its one-line answer. */
function ScreenHeading({ heading, subtitle }: { heading: string; subtitle?: ReactNode }) {
  return (
    // `shrink-0`: in a locked column the content band claims `flex-1` and a header without it
    // is compressed into the grid rather than keeping its own height.
    <header className="flex shrink-0 flex-col gap-field">
      <h1 className="text-page text-ink">{heading}</h1>
      {subtitle ? <p className="max-w-prose text-body text-ink-muted">{subtitle}</p> : null}
    </header>
  )
}

/** The heading a route names itself, read from the registry the nav and the trail also read. */
function RegistryHeading({ subtitle }: { subtitle?: ReactNode }) {
  const heading = labelFor(useLocation().pathname)
  return heading === null ? null : <ScreenHeading heading={heading} subtitle={subtitle} />
}
