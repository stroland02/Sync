/**
 * An abandon reason, bounded, with the remainder one press away.
 *
 * Clamped rather than truncated: the summary says how many characters are behind it, and
 * `<details>` holds the exact text, so nothing is dropped by being bounded.
 */

import { Formatted } from "@/components/status"
import { orAbsent } from "@/lib/format"

/**
 * How much of an abandon reason is shown before the rest has to be asked for.
 *
 * `abandon_reason` is whatever a subprocess wrote, and nothing bounds it: a `tsc` invocation that
 * fails its baseline check puts the compiler's entire `--help` output in this field, which drew a
 * single table row about a thousand pixels tall and pushed every other run off the screen. Nothing
 * that renders it may size itself from untrusted output.
 */
const ABANDON_REASON_PREVIEW = 180

export function AbandonReason({ reason }: { reason: string | null }) {
  const cell = "mt-field font-mono text-meta text-muted-foreground"

  if (reason === null || reason.trim() === "") {
    return (
      <div className={cell}>
        <Formatted value={orAbsent(reason)} />
      </div>
    )
  }
  if (reason.length <= ABANDON_REASON_PREVIEW) {
    return <div className={cell}>{reason}</div>
  }
  return (
    <details className="mt-field">
      <summary className={`${cell} mt-0 cursor-pointer`}>
        {reason.slice(0, ABANDON_REASON_PREVIEW).trimEnd()}&hellip;{" "}
        <span className="underline underline-offset-2">
          show all {reason.length.toLocaleString()} characters
        </span>
      </summary>
      <pre className="mt-field max-h-72 overflow-auto rounded-control border border-line p-row font-mono text-meta whitespace-pre-wrap text-muted-foreground">
        {reason}
      </pre>
    </details>
  )
}
