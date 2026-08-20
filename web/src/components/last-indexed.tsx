/**
 * When the index last finished over one codebase, as a fact tile's value.
 *
 * **Read from `last_index_run`, never from a newest-of stamp**, because that field separates three
 * states a tile would otherwise collapse onto one: never indexed, a pass still in flight, and a
 * pass that finished. A `max(indexed_at)` across call sites answers the third and silently renders
 * the first two as the same nothing.
 *
 * Extracted from `call-sites-dashboards.tsx` at its second caller (the services screen, which
 * replaced a per-vendor freshness card with this one figure). Both read the same query key, so the
 * second mount costs no request.
 *
 * Staleness, never liveness: a repository re-scanned three weeks ago reports that date every day
 * after until another pass moves it, and nothing here implies a pass is running now.
 */

import { useOverview } from "@/api/queries"
import { RelativeTime } from "@/components/relative-time"
import { Skeleton } from "@/components/skeleton"
import { Absent } from "@/components/status"

export function LastIndexed({ repoId }: { repoId: string }) {
  const overview = useOverview(repoId)
  if (overview.isPending) return <Skeleton width="7rem" />
  if (overview.isError) return <Absent>the API did not answer</Absent>
  const pass = overview.data.last_index_run
  if (pass === null) return <Absent>never indexed</Absent>
  if (pass.finished_at === null) return <Absent>a pass started and has not finished</Absent>
  return <RelativeTime iso={pass.finished_at} />
}
