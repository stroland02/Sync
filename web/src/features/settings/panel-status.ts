/**
 * A Settings panel's status band, published where the page's fallback cannot overwrite it.
 *
 * Nine groups count nine different sets, and the page cannot re-derive what a panel fetched.
 */

import { useEffect, useState } from "react"

import { useScreenStatus } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"

export function usePanelStatus(segments: StatusSegment[]) {
  // `ScreenFrame` publishes through the channel a panel publishes through, and React commits a
  // parent's effect after its children's — so About and Pages published once at mount, the page's
  // fallback landed second, and their bands were never seen. One extra commit puts the panel last.
  const [afterMount, setAfterMount] = useState(false)
  useEffect(() => {
    setAfterMount(true)
  }, [])
  useScreenStatus(afterMount ? segments : null)
}
