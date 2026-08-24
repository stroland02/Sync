/**
 * No route matched. Distinct from a 404 out of the API: nothing was asked of the graph.
 *
 * The level count and names are read from `GRAPH_LEVELS` rather than typed out here, on
 * purpose: this sentence went stale once already, claiming five levels after the console had
 * grown a sixth nobody updated it for, and a literal is exactly what drifts silently a second
 * time.
 *
 * This was the one screen wired to `PageHeader`, because the display step had to be mounted
 * somewhere while the feature screens had not adopted the frame yet. `CI-W596` put the last of
 * the twenty-one on `ScreenFrame`, which discharged that reason and left the chassis's own screen
 * as the last thing rendering a component nothing else used. It renders through the same skeleton
 * now, and `PageHeader` is gone.
 */

import { Link, useLocation } from "react-router"

import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"
import { GRAPH_LEVELS } from "@/lib/routes"

export function UnknownRoute() {
  const { pathname } = useLocation()

  // `none` with a reason, which is the vocabulary's answer for a screen that counts nothing. A
  // band rendered empty would read as a count of zero, and zero is a measurement this screen has
  // not taken.
  //
  // The address stays in the body rather than being repeated here: the band said the same
  // sentence as the paragraph below on the first draft, which is one fact written twice and
  // already disagreeing about which of them a reader should believe.
  const status: StatusSegment[] = [
    { kind: "none", why: "no route matched, so nothing was asked of the API" },
  ]

  return (
    <ScreenFrame status={status}>
      <section className="flex flex-col gap-section">
        <h1 className="text-page text-ink">No screen at this address.</h1>
        <p className="max-w-prose text-body text-ink-muted">
          The console has {GRAPH_LEVELS.length} levels, the API Dependency Graph&rsquo;s own. Not
          every level has a screen of its own yet.
        </p>
        <p className="max-w-prose text-body text-ink-muted">
          {GRAPH_LEVELS.join(" → ")}. No route matched{" "}
          <code className="font-mono">{pathname}</code>.
        </p>
        <Link to="/" className="text-body underline underline-offset-2">
          Back to the fleet
        </Link>
      </section>
    </ScreenFrame>
  )
}
