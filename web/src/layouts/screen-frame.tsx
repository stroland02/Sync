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
  status,
  fill = false,
  children,
}: {
  /** Omitted entirely when a screen has nothing to narrow — no element, no rule, no reserved
      height. A bar rendered to say "there is nothing here" is chrome asserting an absence
      nobody asked about. */
  controls?: ReactNode
  /** Required. A screen with nothing to count publishes `{ kind: "none" }` and says why. */
  status: StatusSegment[]
  /** For the two canvases, which computed their own height from the old chassis and would be
      wrong on day one of this one. */
  fill?: boolean
  children: ReactNode
}) {
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
      {controls ? (
        <div
          data-band="controls"
          className="sticky top-12 z-10 flex flex-wrap items-center gap-section border-b border-line bg-background py-field"
        >
          {controls}
        </div>
      ) : null}
      <div
        data-band="content"
        className={fill ? "flex min-h-0 flex-1 flex-col gap-8" : "flex flex-col gap-8"}
      >
        {children}
      </div>
      {/* Fallback for a tree with no provider — tests that render a screen in isolation. */}
      {!target && !publish ? <StatusBand segments={status} /> : null}
    </>
  )
}
