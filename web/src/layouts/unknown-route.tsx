/**
 * No route matched. Distinct from a 404 out of the API: nothing was asked of the graph.
 *
 * The level count and names are read from `GRAPH_LEVELS` rather than typed out here, on
 * purpose: this sentence went stale once already, claiming five levels after the console had
 * grown a sixth nobody updated it for, and a literal is exactly what drifts silently a second
 * time.
 */

import { Link, useLocation } from "react-router"

import { GRAPH_LEVELS } from "@/lib/routes"

export function UnknownRoute() {
  const { pathname } = useLocation()
  return (
    <section className="flex flex-col gap-3">
      <h1 className="text-lg font-medium">No screen at this address.</h1>
      <p className="text-sm text-muted-foreground">
        The console has {GRAPH_LEVELS.length} levels, the API Dependency Graph's own:{" "}
        {GRAPH_LEVELS.join(" → ")}. Not every level has a screen of its own yet. Nothing
        was asked of the API for <code className="font-mono">{pathname}</code>.
      </p>
      <Link to="/" className="text-sm underline underline-offset-2">
        Back to the fleet
      </Link>
    </section>
  )
}
