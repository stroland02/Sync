/**
 * The indexing stream, as the console sees it (decisions 76 and 78).
 *
 * **Two states, and silence is not one of them.** Live or dropped. The server's heartbeat is an
 * SSE comment rather than an event — revised deliberately, because a typed `heartbeat` would put
 * something on the wire corresponding to nothing that happened. A comment never reaches a
 * handler, so this hook cannot observe it and does not try: it keeps the connection warm through
 * a proxy, and a real drop still surfaces because a closed connection raises `onerror`.
 *
 * The consequence worth naming: an idle index and a healthy one look the same here, and that is
 * correct. Neither is a drop, and reporting a difference this hook cannot observe would be the
 * invention the comment exists to avoid.
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
