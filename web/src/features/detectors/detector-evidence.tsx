/**
 * The catalogue's reading pane: what one detector matched, and what its claims rest on.
 *
 * **The rung breakdown is the substance, not an incidental column.** `CLAUDE.md` requires a false
 * positive be attributable to the rung that produced it, and this is where that attribution lands:
 * a detector whose findings rest entirely on `static` is making a claim of one kind, and one
 * mixing `static` and `observed` is making two different kinds of claim under one name.
 *
 * **No precision, accuracy or leaderboard figure, and that is a refusal rather than an omission.**
 * A ratio computed from open findings alone, with no labelled corpus behind it, would measure
 * nothing — and detectors are not competing: more findings is neither better nor worse than fewer.
 *
 * With nothing selected the pane draws the whole set instead of an empty frame: one bar per
 * detector, each a composition of its own findings by rung. That is the one view where the mixes
 * can be compared across detectors without arithmetic, and it is why the pane has two states
 * rather than a placeholder.
 */

import { Suspense, lazy, useMemo, type ReactNode } from "react"
import { Link } from "react-router"

import type { DetectorRow, Tally } from "@/api/types"
import { InfoHint } from "@/components/info-hint"
import { Absent, Formatted } from "@/components/status"
import { SeverityTag } from "@/components/tag"
import { claimParts } from "@/features/detectors/detector-catalogue"
import { rungComposition } from "@/features/detectors/rung-series"
import { orAbsent } from "@/lib/format"

/**
 * `echarts` is ~1.1 MB minified and this screen is one of many. Lazy, so it lands in its own chunk
 * and never in the initial bundle. `fallback={null}` rather than a placeholder: the sentences below
 * it carry the same claims in words and nothing is waiting on the picture.
 */
const RungCompositionChart = lazy(() =>
  import("@/features/detectors/rung-composition-chart").then((mod) => ({
    default: mod.RungCompositionChart,
  })),
)

function plural(count: number, singular: string): string {
  return count === 1 ? singular : `${singular}s`
}

function Heading({ children }: { children: ReactNode }) {
  return <h3 className="furniture text-meta text-ink-muted">{children}</h3>
}

/**
 * One detector's rung tally, each bar a share of that detector's own total.
 *
 * Never a share of anything on another row: two detectors are not compared by length here, only
 * one detector's own rungs against each other. The denominator is printed above.
 */
function RungRows({ tally, total }: { tally: Tally; total: number }) {
  const entries = Object.entries(tally).sort(([a], [b]) => a.localeCompare(b))
  const largest = Math.max(1, ...entries.map(([, count]) => count))

  if (entries.length === 0) {
    return (
      <p className="text-meta text-ink-muted">
        <Absent>no rung recorded</Absent> — this detector&rsquo;s findings carry no provenance
        rung, which is not the same as resting on none.
      </p>
    )
  }

  return (
    <div className="flex min-w-0 flex-col">
      {entries.map(([rung, count]) => (
        <div
          key={rung}
          className="grid grid-cols-[7rem_3rem_minmax(0,1fr)] items-center gap-field border-t border-line py-field first:border-t-0"
        >
          <span className="truncate font-mono text-meta text-ink-muted">
            <Formatted value={orAbsent(rung)} />
          </span>
          <span className="text-right font-mono text-meta tabular-nums">
            {count.toLocaleString()}
          </span>
          <span
            className="h-1.5 overflow-hidden rounded-control bg-secondary"
            role="img"
            aria-label={`${rung}: ${count} of this detector's ${total}`}
          >
            <span
              className="block h-1.5 rounded-control bg-line-strong"
              style={{ width: count === 0 ? "0%" : `${(count / largest) * 100}%` }}
            />
          </span>
        </div>
      ))}
    </div>
  )
}

/** What this detector matched: the kind of change, and the target it was matched against. */
function ClaimRows({ tally }: { tally: Tally }) {
  const entries = Object.entries(tally).sort(([a], [b]) => a.localeCompare(b))

  if (entries.length === 0) {
    return (
      <p className="text-meta text-ink-muted">
        <Absent>no claim recorded</Absent> — the read answered and these findings name no claim,
        which is not the same as matching nothing.
      </p>
    )
  }

  return (
    <div className="flex min-w-0 flex-col">
      {entries.map(([key, count]) => {
        const { kind, target } = claimParts(key)
        return (
          <div
            key={key}
            className="grid grid-cols-[minmax(0,1fr)_3rem] items-baseline gap-row border-t border-line py-field first:border-t-0"
          >
            <span className="flex min-w-0 flex-col gap-field">
              <span className="truncate font-mono text-meta text-ink">
                <Formatted value={orAbsent(kind ?? "")} />
              </span>
              <span className="min-w-0 font-mono text-meta break-all text-ink-muted">
                {target === null ? <Absent>no target recorded</Absent> : target}
              </span>
            </span>
            <span className="text-right font-mono text-meta tabular-nums">
              {count.toLocaleString()}
            </span>
          </div>
        )
      })}
    </div>
  )
}

export function DetectorEvidence({
  row,
  repoId,
}: {
  row: DetectorRow
  repoId: string
}) {
  return (
    <div className="flex min-w-0 flex-col gap-section">
      <p className="flex flex-wrap items-baseline gap-row">
        <span className="text-figure tabular-nums text-ink">{row.total.toLocaleString()}</span>
        <span className="text-body text-ink-muted">
          open {plural(row.total, "finding")} in{" "}
          <code className="font-mono">{repoId}</code> attributed to this detector
        </span>
      </p>

      <section className="flex min-w-0 flex-col gap-field">
        <div className="flex items-center gap-field">
          <Heading>What its claims rest on</Heading>
          <InfoHint label="About this detector's rungs">
            The rung of evidence behind each of this detector&rsquo;s open findings. Each bar is a
            share of this detector&rsquo;s own total — never of another detector&rsquo;s, and never
            of the scope. A rung missing from this list carries none of this detector&rsquo;s
            findings; the ladder beside this pane is the one that reports a measured nought.
          </InfoHint>
        </div>
        <RungRows tally={row.by_rung} total={row.total} />
      </section>

      <section className="flex min-w-0 flex-col gap-field">
        <Heading>By severity, as the vendor published it</Heading>
        <SeverityRows tally={row.by_severity} />
      </section>

      <section className="flex min-w-0 flex-col gap-field">
        <div className="flex items-center gap-field">
          <Heading>What it matched</Heading>
          <InfoHint label="About matched claims">
            One row per claim these findings name: the kind of change matched, and the target it
            was matched against. The count is open findings naming that exact claim — not how often
            the detector ran, which nothing here records.
          </InfoHint>
        </div>
        <ClaimRows tally={row.by_claim} />
      </section>

      <p className="text-meta text-ink-muted">
        No route filters findings by detector yet. Every open finding, by vendor, is on{" "}
        <Link
          to={`/repositories/${encodeURIComponent(repoId)}`}
          className="underline underline-offset-2"
        >
          this repository&rsquo;s own screen
        </Link>{" "}
        instead — that list is not narrowed to this detector.
      </p>
    </div>
  )
}

function SeverityRows({ tally }: { tally: Tally }) {
  const entries = Object.entries(tally).sort(([a], [b]) => a.localeCompare(b))

  if (entries.length === 0) {
    return (
      <p className="text-meta text-ink-muted">
        <Absent>no severity recorded</Absent> — these findings carry none, which is not the same
        as carrying the mildest.
      </p>
    )
  }

  return (
    <div className="flex flex-wrap items-center gap-row">
      {entries.map(([severity, count]) => (
        <span key={severity} className="flex items-center gap-field">
          {severity === "" ? <Absent>unnamed severity</Absent> : <SeverityTag severity={severity} />}
          <span className="font-mono text-meta tabular-nums text-ink-muted">
            {count.toLocaleString()}
          </span>
        </span>
      ))}
    </div>
  )
}

/** With nothing selected: every detector's mix at once, which no single row can show. */
export function EveryDetector({ rows, total }: { rows: readonly DetectorRow[]; total: number }) {
  const composition = useMemo(() => rungComposition([...rows]), [rows])

  return (
    <div className="flex min-w-0 flex-col gap-section">
      <p className="flex flex-wrap items-baseline gap-row">
        <span className="text-figure tabular-nums text-ink">{total.toLocaleString()}</span>
        <span className="text-body text-ink-muted">
          open {plural(total, "finding")} across {rows.length} {plural(rows.length, "detector")},
          each split by the rung behind it
        </span>
      </p>

      <div className="flex flex-col gap-field text-meta text-ink-muted">
        <p className="flex flex-wrap items-center gap-field">
          <span>
            Every bar is full width: these are compositions, not volumes. Each detector&rsquo;s own
            total is printed beside its name.
          </span>
          <InfoHint label="About the composition bars">
            Volume is not encoded here at all. One detector on this screen can hold four
            figures&rsquo; worth of findings and another three, and drawing that as length would
            render the smaller ones as a sliver indistinguishable from nothing — the
            absence-is-not-zero failure arriving through the axis. The rung is a class of evidence
            rather than a position on a good-to-bad scale, so no colour here grades anything: each
            is an identity, named in the legend and in the segment where it fits.
          </InfoHint>
        </p>
        {composition.absentRungs.length > 0 && (
          <p>
            Nothing in this scope rests on{" "}
            {composition.absentRungs.map((rung, index) => (
              <span key={rung}>
                {index > 0 && (index === composition.absentRungs.length - 1 ? " or " : ", ")}
                <code className="font-mono">{rung}</code>
              </span>
            ))}
            . Those rungs keep their place in the legend and draw no segment.
          </p>
        )}
        {composition.unrecognisedRungs.length > 0 && (
          <p>
            One series counts findings whose rung this console does not recognise:{" "}
            {composition.unrecognisedRungs.map((rung, index) => (
              <span key={rung}>
                {index > 0 && ", "}
                <code className="font-mono">{rung}</code>
              </span>
            ))}
            . Counted rather than dropped, so the bars still sum to each detector&rsquo;s own total.
          </p>
        )}
        <p>Choose a detector on the left for what it matched, claim by claim.</p>
      </div>

      {/* Below its own claims rather than above them: the chart is 500px of a pane that is 423px
          at 1920x1080 and half that on a laptop, so anything under it is under the fold. The
          sentences are the claim and go first; the picture is the evidence for them. */}
      <Suspense fallback={null}>
        <RungCompositionChart composition={composition} />
      </Suspense>
    </div>
  )
}
