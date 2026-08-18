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
import { DESTINATIONS, ROUTES } from "@/lib/routes"
import { FleetPage } from "@/features/fleet/fleet-page"

/** What the index asks, since it is no longer a registry entry with a question of its own. */
const WORKSPACE_PICKER_QUESTION =
  "Which workspace do you want to look at? Everything else in this console is one workspace's."
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
function RoutedScreen({
  element: Screen,
  question,
}: {
  element: ComponentType<{ question?: string }>
  question?: string
}) {
  const location = useLocation()
  return (
    <ErrorBoundary key={location.pathname}>
      <Screen question={question} />
    </ErrorBoundary>
  )
}

export default function App() {
  return (
    <Routes>
      <Route element={<AppFrame />}>
        {/* The index is the workspace picker and it is deliberately NOT in `ROUTES`.
            Every registry entry is a page of the selected workspace now; choosing one is chrome,
            and a chooser listed beside the pages it chooses between is the duplication the owner
            saw. It is routed here so `/` resolves and so a reader with no workspace selected lands
            somewhere that can give them one. */}
        <Route
          index
          element={<RoutedScreen element={FleetPage} question={WORKSPACE_PICKER_QUESTION} />}
        />
        {ROUTES.map((route) => (
          <Route
            key={route.path}
            path={route.path.slice(1)}
            element={<RoutedScreen element={route.element} question={route.question} />}
          />
        ))}
        {/* A destination is not a level, and the router does not care: both arrays declare a
            path, an element and the question the header renders. Serving them from one place is
            what keeps `/settings` from being the tenth screen only a typed URL reaches. */}
        {DESTINATIONS.map((destination) => (
          <Route
            key={destination.path}
            path={destination.path.slice(1)}
            element={
              <RoutedScreen element={destination.element} question={destination.question} />
            }
          />
        ))}
        <Route path="*" element={<RoutedScreen element={UnknownRoute} />} />
      </Route>
    </Routes>
  )
}
