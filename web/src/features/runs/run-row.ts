/**
 * What one run row says about itself, derived without rendering anything.
 *
 * Pure on purpose: the console's test charter scopes vitest to classification and derivation, so
 * the four judgements this screen makes about a run are answerable without mounting a table.
 */

import type { RunDisposition, RunRow } from "@/api/types"

/** "in flight" for a run with no disposition yet — never "running", which never arrives here. */
export function describeOutcome(outcome: RunDisposition | null, isRehearsal = false): string {
  if (outcome === null) return "in flight"
  if (outcome === "reported" && isRehearsal) return "halted before the remote"
  return outcome
}

export function isRehearsal(run: RunRow): boolean {
  return (
    run.run_id?.startsWith("rehearsal-") ??
    run.thread_id.split(":")[1]?.startsWith("rehearsal-") ??
    false
  )
}

/** One member of the disposition vocabulary, as a chip offers it. */
export interface DispositionOption {
  /** What `/api/runs?outcome=` accepts. `in-flight` is the transport's word for the null bucket. */
  readonly value: string
  /** `by_disposition`'s key. JSON spells the in-flight bucket `"null"`. */
  readonly bucket: string
}

/**
 * The disposition vocabulary in a fixed order the payload cannot vary.
 *
 * Built from the closed set rather than from `by_disposition`'s keys: the payload omits a
 * disposition no run has reached, and an option missing from the chips claims the value does not
 * exist in the vocabulary — where a zero count is a real answer worth pressing.
 *
 * `parked` is here because it is in `RunDisposition` and in Python's `DISPOSITIONS`. The rail this
 * replaced offered four members and silently asserted that a run waiting on a human is not a thing
 * a run can be.
 */
export const DISPOSITION_OPTIONS: readonly DispositionOption[] = [
  { value: "in-flight", bucket: "null" },
  { value: "opened", bucket: "opened" },
  { value: "reported", bucket: "reported" },
  { value: "parked", bucket: "parked" },
  { value: "abandoned", bucket: "abandoned" },
]

/** What the stream's Record column holds: a recorded line, or the named absence of one. */
export type RecordLine = { text: string; absent?: undefined } | { absent: string; text?: undefined }

/**
 * The one line this run recorded beyond its outcome, or which nothing it is.
 *
 * The reference fills a message column on every row and our runs carry no message field, so this
 * derives one from what the checkpoint actually holds. Every branch returns something: an empty
 * cell would render "we recorded nothing" as "nothing happened", and those are the two readings
 * this console exists to keep apart.
 */
export function recordLine(run: RunRow): RecordLine {
  if (run.outcome === "abandoned") {
    const reason = run.abandon_reason?.trim() ?? ""
    if (reason === "") return { absent: "no reason was recorded" }
    // The head of the string is the part worth a row: the reason opens with the error class and
    // what failed, and degenerates into tool output after the first line.
    return { text: reason.split("\n")[0]!.trim() }
  }
  if (run.outcome === null) {
    if (run.current_node === null || run.current_node === "") {
      return { absent: "no node recorded" }
    }
    return { text: `owed at ${run.current_node}` }
  }
  return { absent: "nothing recorded beyond the outcome" }
}
