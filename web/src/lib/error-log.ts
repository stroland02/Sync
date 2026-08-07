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
 * The grain matches what the surface draws. Dismissing one of ninety-two identical entries removed
 * a row and left ninety-one, which is a control that appears not to work.
 */
export function dismissKind(summary: string): void {
  entries = entries.filter((entry) => entry.summary !== summary)
  notify()
}

export function clearErrors(): void {
  entries = []
  notify()
}

/** One kind of failure, however many times it has happened. */
export interface ErrorKind {
  /** The summary every entry in this group shares — the kind. */
  summary: string
  count: number
  /** The most recent entry of this kind: the one whose detail and timestamp are worth drawing. */
  newest: ErrorEntry
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
    const seen = kinds.get(entry.summary)
    if (seen === undefined) {
      kinds.set(entry.summary, { summary: entry.summary, count: 1, newest: entry })
    } else {
      seen.count += 1
    }
  }
  return [...kinds.values()]
}
