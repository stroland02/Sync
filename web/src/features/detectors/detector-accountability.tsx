/**
 * One card per detector: how many open findings, at which rungs, with what claims and
 * severities.
 *
 * The rung table on each card is the point, not an incidental column. `CLAUDE.md` requires
 * a false positive be attributable to the rung that produced it, and this is where that
 * attribution has to land: a detector whose findings rest entirely on `static` is making a
 * claim of one kind, and one mixing `static` and `observed` is making two different kinds
 * of claim under one name.
 *
 * Order is whatever `GET /api/detectors` returns -- alphabetical by detector name, which is
 * how `sync.dashboard.graph_views.detector_accountability` already sorts it -- and nothing
 * here re-sorts by total. Sorting by count is what turns a roll-up into a leaderboard, and
 * detectors are not competing: more findings is neither better nor worse than fewer.
 *
 * ## Recomposed onto the vendored substrate by M7-W177
 *
 * `docs/superpowers/briefs/2026-08-07-substrate-errors-incidents.md` carries the mapping table
 * and the eleven rulings. Three of them are visible here.
 *
 * **The screen's total moved into the panel whose chart decomposes it.** It was a loose
 * paragraph at `--text-figure` floating above the card, which is the figure register spent with
 * no evidence attached to it; `MetricPanel` is the arrangement that pairs the two.
 *
 * **The rung tally is new, and it answers a question the chart cannot.**
 * `rung-composition-chart.tsx` opens by asking how much of everything the console claims rests on
 * a static read alone, and every bar it draws is normalised to one detector's own total — so that
 * answer appears nowhere on it. `RungSeries.total` has been computed and tested in the data seam
 * since the chart was written and nothing rendered it. A rung nothing rests on renders `0` rather
 * than being suppressed, which is the same claim the paragraph beneath it makes in words.
 *
 * **Two sentences moved down to the rows they are about.** The registry sentence was the third
 * paragraph of the page's intro, two panels above the cards it qualifies; the unscoped-link
 * sentence was rendered once per card, which is one fact written as many times as the graph has
 * detectors. Both are now the catalogue's caption. Every word survives — only the number of
 * copies falls.
 */

import { Suspense, lazy, useMemo } from "react"
import { Link } from "react-router"

import { useDetectors } from "@/api/queries"
import type { BindingSource, DetectorRow, Tally } from "@/api/types"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { MetricPanel } from "@/components/metric-panel"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { Formatted } from "@/components/status"
import {
  CardinalityStatement,
  describeCardinality,
} from "@/features/fleet/cardinality"
import {
  rungComposition,
  type RungComposition as Composition,
} from "@/features/detectors/rung-series"
import { FooterBar } from "@/layouts/footer-bar"
import { describeRung, orAbsent } from "@/lib/format"
import { Card, CardContent, CardHeader } from "@/vendor/supabase/ui/card"

/**
 * `echarts` is ~1.1 MB minified and this screen is one of nine. Lazy, so it lands in its own
 * chunk and never in the initial bundle — the same arrangement `corpus-summary.tsx` makes, and
 * `vite.config.ts`'s `chunkSizeWarningLimit` comment carries why the warning it raises is
 * expected. `fallback={null}` rather than a placeholder: the cards below are the same numbers,
 * already on screen, so nothing is waiting on this.
 */
const RungCompositionChart = lazy(() =>
  import("@/features/detectors/rung-composition-chart").then((mod) => ({
    default: mod.RungCompositionChart,
  })),
)

function isBindingSource(value: string): value is BindingSource {
  return (
    value === "static" ||
    value === "resolved" ||
    value === "observed" ||
    value === "unresolved" ||
    value === "unattributed"
  )
}

/** A tooltip naming what the rung claims, for the one tally whose keys are the rung vocabulary. */
function rungTooltip(key: string): string | undefined {
  return isBindingSource(key) ? describeRung(key) : undefined
}

function plural(count: number, singular: string): string {
  return count === 1 ? singular : `${singular}s`
}

/**
 * The `by_rung` tally, drawn as the mock's inline bar-per-row rather than a table cell.
 *
 * `docs/console-mock/index.html`'s `isDetectors` card (line 489) draws each rung as
 * `112px 40px minmax(0,1fr)`: the rung name, its count right-aligned, then a track with a filled
 * bar. The bar's width is this row's own share of the card's rung total, not a share of anything
 * on another card — two cards are never compared by bar length here, only their own five rungs
 * against each other, the same way `RungComposition`'s stacked bar already refuses to encode
 * volume across detectors as length.
 *
 * `by_claim` and `by_severity` keep the plain `TallyTable` below: the mock's fixture has one rung
 * breakdown per card and nothing for the other two tallies, so there is no drawing to extract for
 * them and no reason to invent one.
 */
function RungBarRows({ tally, tooltipFor }: { tally: Tally; tooltipFor: (key: string) => string | undefined }) {
  const entries = Object.entries(tally).sort(([a], [b]) => a.localeCompare(b))
  const max = Math.max(1, ...entries.map(([, count]) => count))
  return (
    <div className="flex min-w-0 flex-col gap-row">
      <h4 className="furniture text-meta text-ink-muted">By rung</h4>
      <div className="flex flex-col">
        {entries.map(([value, count]) => (
          <div
            key={value}
            className="grid grid-cols-[7rem_2.5rem_minmax(0,1fr)] items-center gap-field border-t border-line py-field"
          >
            <span className="truncate font-mono text-meta text-muted-foreground" title={tooltipFor(value)}>
              <Formatted value={orAbsent(value)} />
            </span>
            <span className="text-right font-mono text-meta tabular-nums">{count.toLocaleString()}</span>
            <span className="h-1.5 overflow-hidden rounded-control bg-secondary">
              <span
                className="block h-1.5 rounded-control bg-ink-muted"
                style={{ width: `${(count / max) * 100}%` }}
              />
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function TallyTable({
  heading,
  tally,
  tooltipFor,
}: {
  heading: string
  tally: Tally
  tooltipFor?: (key: string) => string | undefined
}) {
  const entries = Object.entries(tally).sort(([a], [b]) => a.localeCompare(b))
  return (
    <div className="flex min-w-0 flex-col gap-row">
      {/* `h4` under the card's own `h3`: a tally is contained by the detector it belongs to. */}
      <h4 className="furniture text-meta text-ink-muted">{heading}</h4>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Value</TableHead>
            <TableHead>Findings</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {entries.map(([value, count]) => (
            <TableRow key={value}>
              {/* `value` is a tally key straight from the payload -- an empty string is a
                  real, distinct key (a claim or a severity nothing named), not a missing
                  cell, so it takes the same absence mark as every other unnamed value
                  rather than rendering as blank space with no mark at all. */}
              <TableCell className="font-mono" title={tooltipFor?.(value)}>
                <Formatted value={orAbsent(value)} />
              </TableCell>
              <TableCell className="font-mono">{count.toLocaleString()}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function DetectorCard({ row }: { row: DetectorRow }) {
  return (
    <Card className="flex min-w-0 flex-col">
      <CardHeader>
        {/* Baseline row, name left and the total pushed right by `ml-auto` -- the mock's own
            header shape (`isDetectors`, line 483) for this card, in place of the stacked
            name-then-sentence header this screen drew before the 2026-08-18 layout extraction.
            The total takes `text-figure`, the stat-tile register, because it is now the one
            number a reader scans this card for rather than a clause inside a sentence. */}
        <div className="flex flex-wrap items-baseline gap-field">
          <h3 className="font-mono text-emphasis break-words">{row.detector}</h3>
          <span className="ml-auto font-mono text-figure tabular-nums">
            {row.total.toLocaleString()}
          </span>
        </div>
        <p className="furniture text-meta text-ink-muted">
          open {plural(row.total, "finding")} currently attributed to this detector
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-section">
        <RungBarRows tally={row.by_rung} tooltipFor={rungTooltip} />
        <div className="grid gap-section sm:grid-cols-2">
          <TallyTable heading="By claim" tally={row.by_claim} />
          <TallyTable heading="By severity" tally={row.by_severity} />
        </div>
      </CardContent>
    </Card>
  )
}

/**
 * Every rung this console declares, with what rests on it across the whole scope.
 *
 * The chart above draws each detector's composition and normalises every bar to that detector's
 * own total, so it cannot say how much of everything on this screen rests on one rung. This can,
 * and it is the question the chart's own docstring opens with.
 *
 * A rung nothing rests on renders `0` rather than being dropped, for the reason `rung-series.ts`
 * gives for keeping it as a series: "no open finding here rests on observed traffic" and "this
 * console does not have that rung" are opposite facts about the same picture.
 */
/**
 * The `isDetectors` mock's bottom strip (line 503): a bordered panel, a `text-meta` heading,
 * then `repeat(5, minmax(0,1fr))` columns each carrying a left accent rule, the rung's name, its
 * figure, and a caption -- in place of the two-column table this strip drew before the
 * 2026-08-18 layout extraction. Every rung takes a column whether or not anything rests on it,
 * which is the same "0 draws, absence is not the same fact as not-here" rule the table version
 * already held.
 */
function RungTally({ composition }: { composition: Composition }) {
  return (
    <div className="flex min-w-0 flex-col gap-field rounded-surface border border-line bg-card p-section">
      <h3 className="furniture text-meta text-ink-muted">By rung, across every detector</h3>
      <div className="grid gap-section sm:grid-cols-5">
        {composition.series.map((entry) => (
          <div key={entry.rung} className="border-l border-ink-muted pl-field">
            <div className="font-mono text-meta text-muted-foreground" title={rungTooltip(entry.rung)}>
              {entry.rung}
            </div>
            <div className="font-mono text-figure tabular-nums">{entry.total.toLocaleString()}</div>
          </div>
        ))}
      </div>
      <p className="max-w-prose text-meta text-muted-foreground">
        Counted over every open finding in this scope, once each, by the rung behind it — not
        over the bars above, each of which is a share of one detector's own total.
      </p>
    </div>
  )
}

/**
 * The one chart on this screen, and the sentences that keep it honest.
 *
 * Every bar is full width and carries one detector's composition; the count it is a share of is
 * printed beside the detector's name rather than encoded as length. Both facts are said below
 * rather than left to be inferred, because a stacked bar is exactly where a reader starts
 * reading length as quantity and then as quality.
 *
 * The panel's figure is `total_open_findings` from the payload — the set the chart partitions,
 * and the number this screen already spent the figure register on before the port.
 */
function RungComposition({ rows, total }: { rows: DetectorRow[]; total: number }) {
  const composition = useMemo(() => rungComposition(rows), [rows])

  return (
    <MetricPanel
      label="What these claims rest on"
      metric={{
        value: total.toLocaleString(),
        unit: `open ${plural(total, "finding")} across ${rows.length} ${plural(rows.length, "detector")}`,
      }}
      caption={
        <p className="max-w-prose">
          Every open finding in this scope, split by the rung of evidence behind it, one bar per
          detector. The same counts are in each detector's own <code className="font-mono">By
          rung</code> table below; this is the one view where they can be compared across
          detectors without arithmetic.
        </p>
      }
    >
      <Suspense fallback={null}>
        <RungCompositionChart composition={composition} />
      </Suspense>
      <p className="max-w-prose text-body text-muted-foreground">
        Every bar is the same length because it is a composition, not a quantity: the segments
        are that detector's own findings split by rung, and the number of findings they are a
        share of is printed beside the detector's name. Volume is not encoded here at all —
        one detector on this screen can hold four figures' worth of findings and another
        three, and drawing that as length would render the smaller ones as a sliver
        indistinguishable from nothing.
      </p>
      <p className="max-w-prose text-body text-muted-foreground">
        The rung is a class of evidence, not a position on a good-to-bad scale, so no colour
        here grades anything: each is an identity, and each is named in the legend, in the
        segment where it fits, and in the table beneath. A detector resting entirely on{" "}
        <code className="font-mono">static</code> is not doing worse than one correlating
        watched traffic — it is making a different kind of claim, which is the thing an
        operator weighing a false positive needs first.
      </p>
      <RungTally composition={composition} />
      {composition.absentRungs.length > 0 && (
        <p className="max-w-prose text-body text-muted-foreground">
          Nothing in this scope rests on{" "}
          {composition.absentRungs.map((rung, index) => (
            <span key={rung}>
              {index > 0 && (index === composition.absentRungs.length - 1 ? " or " : ", ")}
              <code className="font-mono">{rung}</code>
            </span>
          ))}
          . Those rungs keep their place in the legend and draw no segment — an absence, which
          is not the same fact as a rung this console does not have.
        </p>
      )}
      {composition.unrecognisedRungs.length > 0 && (
        <p className="max-w-prose text-body text-muted-foreground">
          One series counts findings whose rung this console does not recognise:{" "}
          {composition.unrecognisedRungs.map((rung, index) => (
            <span key={rung}>
              {index > 0 && ", "}
              <code className="font-mono">{rung}</code>
            </span>
          ))}
          . They are counted rather than dropped, so the bars still sum to each detector's own
          total — the provenance vocabulary has grown since this view was written.
        </p>
      )}
    </MetricPanel>
  )
}

/**
 * Why a detector may be missing from a screen that has no registry of them.
 *
 * **Rendered on both branches, and that is the point of it being a component.** It was the page
 * intro's third paragraph before M7-W177, so it appeared over an empty screen as well as over a
 * full one — and the empty screen is where it bites hardest, because "no detector raised
 * anything" and "no detector is installed" are the two readings it exists to keep apart. Moving
 * it down beside the cards without rendering it here would have dropped the qualification on
 * exactly the branch that needs it.
 */
function RegistryNote() {
  return (
    <p className="max-w-prose text-body text-muted-foreground">
      A card here exists only for a detector that has raised an open finding -- the graph keeps
      no registry of which detectors are installed, only the findings they have written. A
      detector currently raising nothing does not appear, and that absence is indistinguishable
      from a detector that does not exist.
    </p>
  )
}

/**
 * The cards, and the two things a reader has to know before reading one.
 *
 * Both sentences below were rendered elsewhere before M7-W177 — the first at the top of the
 * page, two panels above the cards it is about, and the second once inside every card. They are
 * one copy each, here, beside the rows they qualify.
 */
function DetectorCatalogue({ rows, repoId }: { rows: DetectorRow[]; repoId: string }) {
  return (
    <section className="flex min-w-0 flex-col gap-section">
      <div className="flex flex-col gap-field">
        <h2 className="text-section">By detector</h2>
        <RegistryNote />
        {/* No route filters an open finding by the detector that raised it -- that
            attribution exists nowhere else in the console before this screen. The link
            below is real and goes to real findings; it is just not scoped to any row here,
            and the sentence says so rather than letting the link imply otherwise. */}
        <p className="max-w-prose text-body text-muted-foreground">
          No route filters findings by detector yet. Every open finding, by vendor, is on{" "}
          {(
            <Link
              to={`/repositories/${encodeURIComponent(repoId)}`}
              className="underline underline-offset-2"
            >
              this repository's own screen
            </Link>
          )}{" "}
          instead.
        </p>
      </div>
      {/* `repeat(auto-fill, minmax(320px, 1fr))` -- the mock's own card grid (`isDetectors`,
          line 480), replacing the single-column stack this screen drew before the 2026-08-18
          layout extraction. As many columns as fit at 320px each, never fewer than one. */}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(320px,1fr))] gap-section">
        {rows.map((row) => (
          <DetectorCard key={row.detector} row={row} />
        ))}
      </div>
      {/* The record count, under the rows it counts rather than in a heading, and with the
          ordering said out loud. Both facts were argued in this file's docstring and rendered
          nowhere: that order is alphabetical and that nothing re-sorts by total, because sorting
          by count is what turns a roll-up into a leaderboard. `shown` is every row, since this
          catalogue slices nothing — the default would claim a page the screen does not have.
          No pager: `GET /api/detectors` returns the whole roll-up and takes no offset. */}
      <FooterBar
        left={
          <CardinalityStatement
            text={describeCardinality(
              rows.length,
              "detector",
              "detectors",
              "detector name, alphabetically — never by count, which would read as a ranking",
              rows.length,
            )}
          />
        }
      />
    </section>
  )
}

export function DetectorAccountability({ repoId }: { repoId: string }) {
  const query = useDetectors(repoId ?? undefined)

  if (query.isPending) return <LoadingState what="detector accountability" />
  if (query.isError) return <ErrorState error={query.error} what="detector accountability" onRetry={() => void query.refetch()} />

  const { detectors, total_open_findings } = query.data

  if (detectors.length === 0) {
    return (
      <div className="flex flex-col gap-section">
        <EmptyState
          headline={
            `No open finding in ${repoId} is attributed to any detector.`
          }
          detail="The API answered, and the graph holds no open findings in this scope right now. That is an answer, not a failure -- nothing indexed here is currently flagged by any detector."
        />
        <RegistryNote />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-8">
      <RungComposition rows={detectors} total={total_open_findings} />
      <DetectorCatalogue rows={detectors} repoId={repoId} />
    </div>
  )
}
