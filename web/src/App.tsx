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

import type { ComponentType } from "react"
import { Route, Routes, useLocation } from "react-router"

import { ErrorBoundary } from "@/components/error-boundary"
import { ROUTES } from "@/lib/routes"
import { AppFrame } from "@/layouts/app-frame"
import { UnknownRoute } from "@/layouts/unknown-route"

/**
 * One error boundary per routed screen, reset by the address bar.
 *
 * The boundary used to sit in the app shell, outside the `Outlet`, where it survived every
 * navigation — so one crashed screen left the console showing a crash panel for every screen
 * after it, and the only way out was a reload. Keying it by pathname makes navigating away the
 * recovery, including between two findings, which react-router otherwise renders through the
 * same mounted element.
 */
function RoutedScreen({ element: Screen }: { element: ComponentType }) {
  const location = useLocation()
  return (
    <ErrorBoundary key={location.pathname}>
      <Screen />
    </ErrorBoundary>
  )
}

export default function App() {
  return (
    <Routes>
      <Route element={<AppFrame />}>
        {ROUTES.map((route) =>
          route.path === "/" ? (
            <Route key={route.path} index element={<RoutedScreen element={route.element} />} />
          ) : (
            <Route
              key={route.path}
              path={route.path.slice(1)}
              element={<RoutedScreen element={route.element} />}
            />
          )
        )}
        <Route path="*" element={<RoutedScreen element={UnknownRoute} />} />
      </Route>
    </Routes>
  )
}
