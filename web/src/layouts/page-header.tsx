/**
 * The one place a route says what it is and what it is for.
 *
 * **The sentence is not written here and must not be.** `RouteEntry.question` in `lib/routes.ts`
 * already holds one per route, written for exactly this — "What is at risk from this vendor, and
 * what did it change?" — and it has been sitting in the registry unrendered while every screen
 * opened with a bare `h1`. A second copy of that sentence in a feature screen is a sentence that
 * will disagree with the registry, and the registry is what the command palette and the sidebar
 * read.
 *
 * `title` is separate from the question because a route's *label* is generic ("Vendor") and its
 * title is the subject ("seed-console-scale-stripe"). Only the page knows the subject, which is the
 * same reason `Breadcrumbs` takes its trail as a prop rather than deriving it from the URL.
 *
 * **This is the only element on a route permitted `text-display`.** `DESIGN.md`'s Type section adds
 * that step for this component and says so: the console measured a 2.00–2.67:1 type range across
 * all nine routes against a 3.4 bar, and on six of them the widest text was a stat-tile figure — so
 * the eye landed on whichever number happened to be biggest rather than on the thing the screen is
 * about. Two elements at the display step is two focal points, which is none.
 */

import type { ReactNode } from "react"

export function PageHeader({
  title,
  question,
  trail,
  actions,
}: {
  /** The subject, in the operator's terms. Mono is the caller's choice: an id is verbatim, a
   * screen name is not. */
  title: ReactNode
  /** `RouteEntry.question` for this route. Passed rather than looked up, so a screen rendered
   * outside the router — a test, a future embed — cannot fail to have one. */
  question: string
  /** `Breadcrumbs`, when the level has something above it. */
  trail?: ReactNode
  /** At most one primary action, on the right of the title. `ControlBar` carries the rest. */
  actions?: ReactNode
}) {
  return (
    <header className="flex flex-col gap-section">
      {trail}
      <div className="flex flex-wrap items-start justify-between gap-section">
        <div className="flex min-w-0 flex-col gap-field">
          <h1 className="text-display break-words">{title}</h1>
          {/* `max-w-prose` rather than the column's width: the frame is now 40px and the content
              column at 1920px is wide enough to run this sentence past a readable measure, which
              M4.5-W137 measured at 206 characters on the fleet screen before two one-class fixes. */}
          <p className="max-w-prose text-body text-ink-muted">{question}</p>
        </div>
        {actions}
      </div>
    </header>
  )
}
