/**
 * No route matched. Distinct from a 404 out of the API: nothing was asked of the graph.
 */

import { Link, useLocation } from "react-router"

export function UnknownRoute() {
  const { pathname } = useLocation()
  return (
    <section className="flex flex-col gap-3">
      <h1 className="text-lg font-medium">No screen at this address.</h1>
      <p className="text-sm text-muted-foreground">
        The console has five levels: the fleet, the codebase overview, a vendor, a finding,
        and its solution workflow. Nothing was asked of the API for{" "}
        <code className="font-mono">{pathname}</code>.
      </p>
      <Link to="/" className="text-sm underline underline-offset-2">
        Back to the fleet
      </Link>
    </section>
  )
}
