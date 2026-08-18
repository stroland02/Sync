/**
 * The indexing stream, as the console sees it (decisions 76 and 78).
 *
 * **Three states, kept apart deliberately.** Connected and quiet, connected and arriving, and
 * dropped. Decision 76 requires a dropped stream to be rendered rather than hidden, and a drop can
 * only be rendered if it is distinguishable from silence — which is what the server's named
 * heartbeat buys and what this hook exists to preserve. A hook that reported "no events lately"
 * for both would put the console back where the payload started.
 *
 * **A heartbeat never moves a domain count.** It asserts that the stream is alive and nothing
 * else; counting it would be the console inventing work that did not happen.
 *
 * **The count is kept on drop rather than reset.** Freeze and name: what arrived before the
 * connection ended is evidence that genuinely arrived, and discarding it would throw away a true
 * fact to render an absence.
 *
 * `EventSource` reconnects natively on error, which is why `status` is what it is: this hook
 * reports what it currently has, and the screen decides what to say. It does not claim the index
 * is still running, because nothing records that.
 */

import { useEffect, useRef, useState } from "react"

export type StreamStatus = "live" | "dropped"

export interface RepositoryEvents {
  /** Call sites the stream has reported since this subscription opened. Never includes heartbeats. */
  readonly indexedCount: number
  readonly status: StreamStatus
}

export function useRepositoryEvents(repoId: string): RepositoryEvents {
  const [indexedCount, setIndexedCount] = useState(0)
  const [status, setStatus] = useState<StreamStatus>("live")
  const sourceRef = useRef<EventSource | null>(null)

  useEffect(() => {
    // The scope is in the path, per decision 49 — never a query string.
    const source = new EventSource(`/api/repositories/${encodeURIComponent(repoId)}/events`)
    sourceRef.current = source

    source.addEventListener("call_site.indexed", () => {
      setIndexedCount((count) => count + 1)
      setStatus("live")
    })

    // Named rather than a comment, so the console can tell alive-and-quiet from gone. It carries
    // no domain fact and moves no count.
    source.addEventListener("heartbeat", () => {
      setStatus("live")
    })

    source.onerror = () => {
      setStatus("dropped")
    }

    return () => {
      // A closed tab releases its listening connection immediately. The route holds the stream
      // open with no lifetime cap by owner selection, which makes this cleanup the only thing
      // bounding connection use.
      source.close()
    }
  }, [repoId])

  return { indexedCount, status }
}
