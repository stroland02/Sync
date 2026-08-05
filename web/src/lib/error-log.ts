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

export function dismissError(id: string): void {
  entries = entries.filter((entry) => entry.id !== id)
  notify()
}

export function clearErrors(): void {
  entries = []
  notify()
}
