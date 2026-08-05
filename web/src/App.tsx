/**
 * The routes are the API Dependency Graph, one level per screen.
 *
 * Deep links are the point: an operator shares `/findings/f-91ac` with a colleague and the
 * colleague lands on the finding, not on a shell that has forgotten what was being looked at.
 *
 * Every `<Route>` below is built from `lib/routes.ts` rather than written by hand. A route
 * that is not in that registry cannot be declared, because this is the only place that reads
 * it into the router — the same array the navigation and the command palette read.
 */

import { Route, Routes } from "react-router"

import { ROUTES } from "@/lib/routes"
import { AppShell } from "@/layouts/app-shell"
import { UnknownRoute } from "@/layouts/unknown-route"

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        {ROUTES.map((route) =>
          route.path === "/" ? (
            <Route key={route.path} index element={<route.element />} />
          ) : (
            <Route
              key={route.path}
              path={route.path.slice(1)}
              element={<route.element />}
            />
          )
        )}
        <Route path="*" element={<UnknownRoute />} />
      </Route>
    </Routes>
  )
}
