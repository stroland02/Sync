/**
 * The console's central record of genuine failures.
 *
 * A store outside React, because the three sources that feed it — a query's background
 * poll, an unhandled promise rejection, and a render crash — do not share a common
 * component ancestor. Keeping the list here lets all three reach the same surface instead
 * of each inventing its own.
 */

export interface ErrorEntry {
  id: string
  summary: string
  path?: string
  status?: number
  detail: string
  timestamp: string
}

export interface FailureInput {
  summary: string
  path?: string
  status?: number
  detail: string
}

let entries: ErrorEntry[] = []
let nextId = 0
const listeners = new Set<() => void>()

function notify(): void {
  for (const listener of listeners) listener()
}

export function subscribeErrors(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** Newest first, so the count in the header and the top of the list always agree. */
export function getErrorEntries(): ErrorEntry[] {
  return entries
}

export function reportError(failure: FailureInput): void {
  nextId += 1
  entries = [{ id: String(nextId), timestamp: new Date().toISOString(), ...failure }, ...entries]
  notify()
}

/**
 * Every entry of one kind, dismissed together.
 *
 * The grain matches what the surface draws, and it has to be the same grain in both directions.
 * Dismissing one of ninety-two identical entries removed a row and left ninety-one, which is a
 * control that appears not to work; dismissing by summary alone cleared entries from endpoints the
 * dismissed row had never named, which is a control that quietly does more than it says.
 *
 * `key` is `ErrorKind.key`, so the caller cannot pass a grain the grouping does not use.
 */
export function dismissKind(key: string): void {
  entries = entries.filter((entry) => kindKey(entry) !== key)
  notify()
}

export function clearErrors(): void {
  entries = []
  notify()
}

/** One kind of failure, however many times it has happened. */
export interface ErrorKind {
  /** What identifies this group: the summary and the endpoint together. `dismissKind` takes it. */
  key: string
  /** The summary every entry in this group shares. */
  summary: string
  count: number
  /** The most recent entry of this kind: the one whose detail and timestamp are worth drawing. */
  newest: ErrorEntry
}

/**
 * What makes two failures the same kind: the summary **and** the endpoint.
 *
 * The summary alone is not enough, and this is the whole of it. `describe-failure.ts` writes the
 * status into the summary and the endpoint into its own field, so *"The API answered with HTTP
 * 502."* is what every failing route says during one outage. Keyed on the summary, five failures
 * across three endpoints drew one row printing one path beside "5 times" — a count attributing four
 * failures to a route that produced one of them, which is the console asserting something untrue
 * about its own graph.
 *
 * A failure with no endpoint — a render crash — keys on the empty string, so it stays its own row
 * rather than folding into whichever API failure happens to share its wording.
 */
function kindKey(entry: ErrorEntry): string {
  return `${entry.summary} ${entry.path ?? ""}`
}

/**
 * How many kinds the surface draws before it states a count instead.
 *
 * Three is enough to show that failures differ and few enough that the banner never becomes the
 * page. The cap is presentation: nothing below is dropped from the log.
 */
export const KINDS_SHOWN = 3

/**
 * The log collapsed to one row per kind, newest kind first.
 *
 * The measured failure this exists for: a console with no API behind it accumulated ninety-two
 * *"The API is unreachable"* entries and stacked ninety-two cards over the page. Every one was a
 * genuine failure and none was a second piece of information — one poll failing repeatedly is one
 * kind with a count, and a reader needs the count rather than the repetition.
 *
 * Reads the whole array rather than a window of it, so the counts are counts over the log and not
 * over what happens to be drawn.
 */
export function groupErrorsByKind(log: readonly ErrorEntry[]): ErrorKind[] {
  const kinds = new Map<string, ErrorKind>()
  for (const entry of log) {
    const key = kindKey(entry)
    const seen = kinds.get(key)
    if (seen === undefined) {
      kinds.set(key, { key, summary: entry.summary, count: 1, newest: entry })
    } else {
      seen.count += 1
    }
  }
  return [...kinds.values()]
}
