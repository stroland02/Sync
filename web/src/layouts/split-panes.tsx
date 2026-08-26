/**
 * Two peer panes under one header, each scrolling its own body inside a locked viewport.
 *
 * `detail-grid.tsx` is the console's rail-and-content shape: a narrow column that *describes*
 * the wide one beside it. This is the other two-column shape, and the difference is not width —
 * it is that neither half is subordinate. Evidence on one side, what the evidence produced on the
 * other, both visible at once, neither summarising the other. A fourth entry in `DetailGrid`'s
 * `SHAPE` map would have described two peers as a rail, which is why this is a separate file.
 *
 * **5fr : 7fr is the Stitch reference's own `lg:w-5/12` / `lg:w-7/12`, taken verbatim.** At 1440×900
 * with the collapsed sidebar and the frame gutter that is 533px and 747px. The wide half is the
 * remediation half because the diff and the compiler output live there and a diff has a minimum
 * readable measure; the evidence half carries a marker rail and prose, which do not.
 *
 * **The disagreement, recorded rather than resolved silently** (`web/CLAUDE.md` requires it): the
 * retired console mock drew this screen as a 300px checklist beside a wide activity list — the
 * width `DetailGrid`'s `narrow` shape still carries, and the only place that literal appears. The
 * Stitch set is the primary visual authority and it draws two near-peers; our left pane also holds
 * evidence cards and a marker rail, which 300px cannot hold. The mock loses.
 *
 * **Below `lg` the panes stack and each still owns its own scroll**, which is a deliberate
 * departure from the spec's "the page scrolls normally". A screen at `layout="locked"` stamps
 * `data-screen="locked"` at every width, so `main` is `overflow-hidden` at every width and a page
 * that expected to scroll would be clipped instead. Two half-height scrollers is worse reading
 * than one column and it is not a lie about what is on screen; clipping is.
 *
 * No transition on any pane geometry and no drag handle. The first is held by
 * `test_console_design_tokens.py::test_nothing_transitions_geometry_anywhere`; the second is not in
 * the reference and a split a reader can drag is state the URL does not carry.
 */

import type { ReactNode } from "react"

export function SplitPanes({
  header,
  left,
  right,
}: {
  /** Spans both panes, never scrolls: what this page is about, held still. */
  header: ReactNode
  /** The narrow half — what the run read and did. */
  left: ReactNode
  /** The wide half — what it produced and what checked it. */
  right: ReactNode
}) {
  return (
    // `left` and `right` are grid children directly, so each pane owns its own internals — the
    // same contract `detail-grid.tsx` states, and for the same reason: a wrapper here would
    // silently overwrite a per-pane decision the caller already made.
    <section className="grid min-h-0 min-w-0 flex-1 grid-rows-[auto_minmax(0,1fr)_minmax(0,1fr)] gap-8 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:grid-rows-[auto_minmax(0,1fr)]">
      <div className="min-w-0 lg:col-span-2">{header}</div>
      {left}
      {right}
    </section>
  )
}
