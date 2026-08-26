/**
 * What everything this scope claims rests on, one rung at a time.
 *
 * **This is the console's own argument rendered as a chart, and it took two tries to get the form
 * right.** It shipped as a donut, and a donut asserts share-of-whole, which cannot draw a zero:
 * against a statically indexed codebase four of the five rungs are measured noughts, so it drew
 * one closed ring with a one-entry legend and read as broken. A horizontal bar has a length of
 * zero and still has a row, a label and a printed count, so a rung at nought reads as *measured
 * and empty* rather than as missing.
 *
 * **A zero here is a measurement, and this is nearly the only place on the console where that is
 * true.** `detector_accountability` seeds the tally from the whole rung vocabulary rather than
 * from the rows it found, so `unattributed: 0` means counted-and-found-none — the opposite of the
 * usual reading, where a missing key means nobody looked. A rung the payload omits entirely is
 * therefore a different fact again, and it is named in words rather than drawn as a nought.
 *
 * **`unattributed` is drawn like any other rung.** It is the count the honesty rule exists to make
 * visible, and hiding it would be the one edit that defeats the panel's purpose.
 *
 * Merged here from the page's second rung panel on 2026-08-26: `bindings_by_rung` on the Overview
 * payload and `by_rung` on this one are the same population counted the same way, and the screen
 * drew both. One fact rendered twice is the shape that eventually disagrees with itself.
 */

import { InfoHint } from "@/components/info-hint"
import { RankedBars } from "@/components/ranked-bars"
import type { RungLadder as Ladder } from "@/features/detectors/detector-catalogue"

export function RungLadder({ ladder, repoId }: { ladder: Ladder; repoId: string }) {
  // Only what was reported reaches the bars. A declared rung the payload omitted has no count to
  // draw, and drawing it at nought would report a measurement nobody took.
  const rows = ladder.rows
    .filter((row) => row.count !== null)
    .map((row) => ({ key: row.rung, value: row.count as number }))

  const meanings = new Map(ladder.rows.map((row) => [row.rung, row.meaning]))

  return (
    <div className="flex min-w-0 flex-col gap-section">
      <RankedBars
        label="What these claims rest on"
        caption={`Every open finding in ${repoId}, counted once by the rung of evidence behind it — strongest evidence first, never by count. A rung at nought was counted and found empty.`}
        rows={rows}
        unit="open findings"
        colourByKey={false}
        annotate={(rung) => meanings.get(rung) ?? "a rung this console does not recognise"}
        // The rungs partition every open finding exactly once, so a share of the total is a claim
        // this set supports — which is not true of most rankings this component draws.
        share
        max={rows.length}
      />

      <div className="flex flex-col gap-field text-meta text-ink-muted">
        <p className="flex flex-wrap items-center gap-field">
          <span>
            Counted over open findings once each — not over one detector&rsquo;s own share.
          </span>
          <InfoHint label="About the rung ladder">
            A detector&rsquo;s own rung breakdown is a share of that detector&rsquo;s total, so the
            per-detector bars beside this one cannot be added up. This ladder counts the scope
            directly: every open finding in{" "}
            <code className="font-mono">{repoId}</code> once, by the rung behind it. The rung is a
            class of evidence, not a position on a good-to-bad scale — a claim resting on{" "}
            <code className="font-mono">static</code> is not worse than one correlating watched
            traffic, it is a different kind of claim, which is what an operator weighing a false
            positive needs first.
          </InfoHint>
        </p>

        {ladder.countedEmpty.length > 0 && (
          <p>
            Nothing here rests on <RungList rungs={ladder.countedEmpty} />. Counted and found
            empty — an absence, not a rung this console does not have.
          </p>
        )}

        {ladder.unreported.length > 0 && (
          <p>
            The read did not report <RungList rungs={ladder.unreported} /> at all. Not a nought:
            this tally is filled from the whole rung vocabulary, so a missing rung is the transport
            falling behind rather than a measurement.
          </p>
        )}

        {ladder.unrecognised.length > 0 && (
          <p>
            <RungList rungs={ladder.unrecognised} /> {ladder.unrecognised.length === 1 ? "is" : "are"}{" "}
            outside this console&rsquo;s vocabulary and counted rather than dropped, so the bars
            still sum to the scope&rsquo;s own total.
          </p>
        )}
      </div>
    </div>
  )
}

function RungList({ rungs }: { rungs: readonly string[] }) {
  return (
    <>
      {rungs.map((rung, index) => (
        <span key={rung}>
          {index > 0 && (index === rungs.length - 1 ? " or " : ", ")}
          <code className="font-mono">{rung}</code>
        </span>
      ))}
    </>
  )
}
