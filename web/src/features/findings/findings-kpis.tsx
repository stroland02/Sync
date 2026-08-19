/**
 * Dashboard F1: the Findings page's opening facts.
 *
 * **Two of the catalogue's three Findings dashboards are deliberately not built, and the reasons
 * belong here rather than in a plan nobody opens while editing this file.**
 *
 * - **F2, a severity donut, is refused as a duplicate.** This page already renders the severity
 *   distribution — `TriageTabs` carries one tab per kind with an exact count, computed without
 *   the severity narrowing applied. A donut beside it would draw the same numbers a second way,
 *   and the owner's ruling is severity once per page, scoped differently. The tabs are also
 *   strictly better here: they are the control that narrows the table, so the distribution and
 *   the filter are one thing rather than a chart and a control that agree until one drifts.
 * - **F3, findings per integration, is built on the Integrations page** (`findings-per-integration
 *   .tsx`). One chart, one home. The catalogue proposed it on both screens, and a fact written
 *   twice disagrees with itself eventually — which is `CLAUDE.md`'s most expensive form of debt
 *   because the disagreement is silent.
 *
 * **So this strip earns its slot by carrying what the tabs and the table do not**: how much is
 * dismissed rather than open, how many detectors stood behind the answer, and when the workspace
 * was last indexed. None of those is a row on this page, and the third is what tells a reader
 * whether an empty screen means clean or means nothing looked.
 */

import type { VendorFindingsPage } from "@/api/types"
import { KpiStrip } from "@/components/kpi-strip"
import { RelativeTime } from "@/components/relative-time"
import { Absent } from "@/components/status"

export function FindingsKpis({
  page,
  detectorNames,
}: {
  page: VendorFindingsPage
  /** The detector roll-up's names, or null when that route did not answer. */
  detectorNames: string[] | null
}) {
  // No dismissal tile, and that is a scope decision rather than an omission: dismissals are
  // fleet-wide (a dismissal records no `repo_id`) and every tile below is this workspace's.
  // One row mixing the two scopes is the attribution error this console keeps removing --
  // `DismissedTally` renders that figure beneath, where it can state its own scope in a caption.
  return (
    <KpiStrip
      items={[
        {
          label: "Open findings",
          value: page.severity_total.toLocaleString(),
          note: "counted before any narrowing on this page",
        },
        {
          label: "Kinds present",
          value: Object.values(page.severity_counts).filter((n) => n > 0).length.toLocaleString(),
          note: `of ${page.severity_order.length} in the vocabulary`,
        },
        {
          label: "Detectors reporting",
          value:
            detectorNames === null ? (
              <Absent>the roll-up did not answer</Absent>
            ) : (
              detectorNames.length.toLocaleString()
            ),
          // Which is the difference between "clean" and "nothing checked", and it is the one
          // fact on this page that makes an empty table readable.
          note:
            detectorNames === null
              ? "so this page cannot say what checked this workspace"
              : "stood behind this answer, including the zeros",
          figure: detectorNames !== null,
        },
        {
          label: "Last indexed",
          value:
            page.indexed_at === null ? (
              <Absent>never recorded</Absent>
            ) : (
              <RelativeTime iso={page.indexed_at} />
            ),
          note:
            page.indexed_at === null
              ? "nothing has walked this workspace, so nothing here is a measurement"
              : "when INDEX last wrote a call site here",
          figure: false,
        },
      ]}
    />
  )
}
