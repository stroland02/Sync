/**
 * The routes are the API Dependency Graph, one level per screen.
 *
 * Deep links are the point: an operator shares `/findings/f-91ac` with a colleague and the
 * colleague lands on the finding, not on a shell that has forgotten what was being looked at.
 */

import { Route, Routes } from "react-router"

import { FindingPage } from "@/features/findings/finding-page"
import { FleetPage } from "@/features/fleet/fleet-page"
import { OverviewPage } from "@/features/repositories/overview-page"
import { VendorPage } from "@/features/vendors/vendor-page"
import { WorkflowPage } from "@/features/workflows/workflow-page"
import { AppShell } from "@/layouts/app-shell"
import { UnknownRoute } from "@/layouts/unknown-route"

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<FleetPage />} />
        <Route path="codebase" element={<OverviewPage />} />
        <Route path="vendors/:vendorId" element={<VendorPage />} />
        <Route path="findings/:findingId" element={<FindingPage />} />
        <Route path="findings/:findingId/workflow" element={<WorkflowPage />} />
        <Route path="*" element={<UnknownRoute />} />
      </Route>
    </Routes>
  )
}
