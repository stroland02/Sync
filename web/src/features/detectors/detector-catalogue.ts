/**
 * The four classifications this catalogue turns on, each with a wrong answer that would put a
 * false claim on screen.
 *
 * **Which nothing an empty catalogue is.** A detector that has never fired, a corpus nothing has
 * ever read, and a read that has not answered are three different facts, and the payload alone
 * cannot tell them apart — `GET /api/detectors` returns an empty list for all three. The corpus
 * answer is a second read, and `catalogueState` is where the two are joined. Collapsing them is
 * how "nothing has ever indexed this repository" gets rendered as "no detector found anything",
 * which is the console's own worst failure told about itself.
 *
 * **A declared rung the payload did not report is not a rung at nought.**
 * `DetectorAccountabilityResponse.by_rung` seeds its tally from the whole rung vocabulary, so a
 * missing key is a transport defect rather than an absence — and drawing it as `0` would report a
 * measurement nobody made. `rungLadder` carries `null` for it and `0` for a rung that was counted
 * and found empty.
 *
 * **A claim key is two facts joined by a colon** — the kind of change matched, and the target it
 * was matched against — and either half can be missing. Splitting is done here rather than in the
 * renderer so a key the transport grows a new shape for lands on `null`, not on a mis-sliced
 * string.
 */

import { BINDING_SOURCES } from "@/api/types"
import type { BindingSource, DetectorRow, Tally } from "@/api/types"
import { describeRung } from "@/lib/format"

/**
 * Strongest evidence first, which is the order an operator weighs them in — never by count. A
 * ladder reordered by its own data reads differently on every visit and invites the ranking
 * reading the rung vocabulary does not support.
 */
export const RUNG_ORDER: readonly string[] = [
  "observed",
  "resolved",
  "static",
  "unresolved",
  "unattributed",
]

export type CatalogueState =
  /** Nothing has ever read this repository, so no detector could have fired against it. */
  | "never-indexed"
  /** The corpus was read and no open finding here is attributed to any detector. */
  | "counted-zero"
  /** The catalogue is empty and the corpus read has not answered, so which nothing is unknown. */
  | "corpus-unknown"
  | "populated"

export interface CorpusAnswer {
  /** The newest call site index time, or `null` when no call site here carries one. */
  readonly indexedAt: string | null
  /** Whether the graph holds an index pass for this repository at all. */
  readonly hasIndexRun: boolean
}

export function catalogueState(input: {
  readonly detectorCount: number
  readonly corpus: CorpusAnswer | "unanswered"
}): CatalogueState {
  if (input.detectorCount > 0) return "populated"
  if (input.corpus === "unanswered") return "corpus-unknown"
  if (input.corpus.indexedAt === null && !input.corpus.hasIndexRun) return "never-indexed"
  return "counted-zero"
}

export interface RungRow {
  readonly rung: string
  /**
   * `null` when the payload did not carry this declared rung at all — which the transport's own
   * contract says cannot happen, and which is therefore not a zero. `0` is a measurement.
   */
  readonly count: number | null
  /** False for a rung this console's vocabulary does not hold. Drives the wording, never a hue. */
  readonly known: boolean
  readonly meaning: string
}

export interface RungLadder {
  /** Every declared rung in evidence order, then whatever the transport has grown, sorted. */
  readonly rows: readonly RungRow[]
  /** What the reported counts sum to — the denominator every share on this ladder is taken over. */
  readonly total: number
  /** Declared rungs carrying at least one open finding. */
  readonly carrying: readonly string[]
  /** Declared rungs counted and found empty. An absence that was measured. */
  readonly countedEmpty: readonly string[]
  /** Declared rungs the payload did not report. Not empty — unreported. */
  readonly unreported: readonly string[]
  /** Keys outside this console's vocabulary, counted rather than dropped. */
  readonly unrecognised: readonly string[]
}

export function rungLadder(byRung: Tally): RungLadder {
  const declared = new Set<string>(BINDING_SOURCES)
  const rows: RungRow[] = RUNG_ORDER.map((rung) => ({
    rung,
    count: rung in byRung ? byRung[rung] : null,
    known: true,
    meaning: describeRung(rung as BindingSource),
  }))

  const unrecognised = Object.keys(byRung)
    .filter((key) => !declared.has(key))
    .sort()
  for (const rung of unrecognised) {
    rows.push({
      rung,
      count: byRung[rung],
      known: false,
      meaning: "a rung this console does not recognise",
    })
  }

  const reported = rows.filter((row) => row.count !== null)
  return {
    rows,
    total: reported.reduce((sum, row) => sum + (row.count ?? 0), 0),
    carrying: rows.filter((row) => row.known && (row.count ?? 0) > 0).map((row) => row.rung),
    countedEmpty: rows.filter((row) => row.known && row.count === 0).map((row) => row.rung),
    unreported: rows.filter((row) => row.known && row.count === null).map((row) => row.rung),
    unrecognised,
  }
}

export interface ClaimParts {
  /** The kind of change matched. `null` when the key names none. */
  readonly kind: string | null
  /** What it was matched against. `null` when the key carries no target. */
  readonly target: string | null
}

/** `claim-removed:/id_token/claims/sub` → the kind and the pointer it was matched against. */
export function claimParts(key: string): ClaimParts {
  const at = key.indexOf(":")
  if (at === -1) return { kind: key === "" ? null : key, target: null }
  const kind = key.slice(0, at)
  // Only the first colon splits: a JSON pointer and a protobuf path both carry more of them, and
  // slicing at the last one would move most of the target into the kind.
  const target = key.slice(at + 1)
  return { kind: kind === "" ? null : kind, target: target === "" ? null : target }
}

/**
 * The distinct kinds of change every detector in this scope matched, sorted.
 *
 * The tally's keys are one per matched target, so counting them counts pointers rather than the
 * shapes of change Sync looks for — which is the figure this screen is a catalogue of.
 */
export function claimKinds(rows: readonly DetectorRow[]): string[] {
  const kinds = new Set<string>()
  for (const row of rows) {
    for (const key of Object.keys(row.by_claim)) {
      const { kind } = claimParts(key)
      if (kind !== null) kinds.add(kind)
    }
  }
  return [...kinds].sort()
}

export type Selection =
  | { readonly state: "none" }
  | { readonly state: "resolved"; readonly row: DetectorRow }
  /** The address names a detector this roll-up does not hold. Carried back so the pane can say so. */
  | { readonly state: "unresolved"; readonly key: string }

export function selectDetector(rows: readonly DetectorRow[], key: string | null): Selection {
  if (key === null || key === "") return { state: "none" }
  const row = rows.find((candidate) => candidate.detector === key)
  return row === undefined ? { state: "unresolved", key } : { state: "resolved", row }
}
