/**
 * The Runs strip's own read, so the strip can sit at the top of the page.
 *
 * **It lived inside `RunsCard` and that put it in the wrong place.** The card renders below a
 * paragraph of scope caveats and a filter rail, so the strip opened halfway down the screen while
 * every other page opens with one — the uniformity the owner asked for is the point, and a strip
 * a reader has to scroll to is not a strip.
 *
 * **`limit: 1` is the whole trick.** Every figure the strip needs is `by_disposition` and
 * `unfiltered_total`, which `sync.dashboard.fleet.runs` computes over every run *before* the
 * outcome filter applies — so this asks for one row and reads the totals off the envelope. The
 * card's own query keeps whatever page and narrowing the reader chose, and the two cannot
 * disagree because both figures come from the same unfiltered computation rather than from the
 * page each happens to be showing.
 *
 * A second request rather than a shared cache entry, and deliberately: sharing would mean pinning
 * the card to the strip's parameters, which would take the pager and the rail away from the
 * reader to save one small read.
 */

import { useRuns } from "@/api/queries"
import { ErrorState, LoadingState } from "@/components/states"
import { RunsKpis } from "@/features/runs/runs-kpis"

export function RunsKpisRegion() {
  const query = useRuns({ limit: 1, offset: 0, outcome: null })

  if (query.isPending) return <LoadingState what="the run totals" />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what="the run totals"
        onRetry={() => void query.refetch()}
      />
    )
  }
  return <RunsKpis page={query.data} />
}
