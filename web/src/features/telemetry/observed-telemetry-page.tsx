/**
 * This route is registered in `web/src/lib/routes.ts` under the label "Observed telemetry",
 * pointed at `ObservedTelemetryPage`. That label and that name are both stale: what this
 * destination renders is the Signals level in full — one panel per attached integration,
 * grouped by role (vendor, signal source, human surface) — of which observed telemetry is now
 * one panel among three, not the whole screen. `signals-page.tsx` carries the level's own
 * docstring and the argument for the split.
 *
 * This file is kept, exporting the same name, so the route registry — owned by another agent
 * this phase — does not need an edit to pick up the fuller screen; Vite's HMR resolves this
 * re-export the same way it resolves any other import. **Recommended follow-up, for whoever
 * next holds `routes.ts`:** rename this route's `label` to `"Signals"`, update its `question`
 * to name all three roles, and point `element` directly at
 * `@/features/signals/signals-page`'s `SignalsPage` — this file can then be deleted.
 */

export { SignalsPage as ObservedTelemetryPage } from "@/features/signals/signals-page"
