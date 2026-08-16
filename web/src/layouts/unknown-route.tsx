/**
 * No route matched. Distinct from a 404 out of the API: nothing was asked of the graph.
 *
 * The level count and names are read from `GRAPH_LEVELS` rather than typed out here, on
 * purpose: this sentence went stale once already, claiming five levels after the console had
 * grown a sixth nobody updated it for, and a literal is exactly what drifts silently a second
 * time.
 *
 * **This is the chassis's own screen, so it is the one route M7-W160 wires to `PageHeader`.** The
 * item's constraint is that nothing in `features/` changes — the nine feature screens keep rendering
 * exactly what they render today inside the new frame, which is what makes the frame reviewable
 * separately from the pages. That leaves the display step declared, guarded, and mounted nowhere;
 * wiring it here proves it renders and gives the next item a worked example rather than a
 * description. The nine screens adopt it in M7's next work item, and the type range does not move
 * until they do.
 */

import { Link, useLocation } from "react-router"

import { PageHeader } from "@/layouts/page-header"
import { GRAPH_LEVELS } from "@/lib/routes"

export function UnknownRoute() {
  const { pathname } = useLocation()
  return (
    <>
      <PageHeader
        title="No screen at this address."
        question={`The console has ${GRAPH_LEVELS.length} levels, the API Dependency Graph's own. Not every level has a screen of its own yet.`}
      />
      <section className="flex flex-col gap-section">
        <p className="max-w-prose text-body text-ink-muted">
          {GRAPH_LEVELS.join(" → ")}. Nothing was asked of the API for{" "}
          <code className="font-mono">{pathname}</code>.
        </p>
        <Link to="/" className="text-body underline underline-offset-2">
          Back to the fleet
        </Link>
      </section>
    </>
  )
}
