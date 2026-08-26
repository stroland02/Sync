/**
 * Dashboard T1: the Trends page's opening facts.
 *
 * **Every tile is a window total, and the window is "everything recorded" rather than a period.**
 * Neither series route takes a date range, so a tile saying "this month" would be a claim the
 * payload cannot support. What the tiles say instead is what the two charts below sum to, which
 * is the honest reading and the one that makes the charts checkable against them.
 *
 * **The two totals are not comparable and the notes say so.** Findings are Sync's output;
 * changes are the vendors' output. Their ratio is meaningless — most changes touch nothing this
 * codebase calls, which is the product working — so they sit as two counts and nothing here
 * divides one by the other.
 *
 * **`still_open` is beside `total`, never instead of it.** The findings series counts what DETECT
 * produced including findings since closed, because a series filtered to still-open findings
 * shrinks its own past every time a patch lands. The tile pair keeps both questions visible.
 */

import { useQuery } from "@tanstack/react-query"

import { useFindingsOverTime } from "@/api/queries"
import { fetchChangesOverTime } from "@/features/dashboards/daily-series"
import { KpiStrip } from "@/components/kpi-strip"
import { Absent } from "@/components/status"

export function TrendsKpis() {
  const findings = useFindingsOverTime(null)
  const changes = useQuery({
    // The changes card's key, so the strip and the chart share one read.
    queryKey: ["integration-changes", "over-time"],
    queryFn: ({ signal }) => fetchChangesOverTime(signal),
  })

  const pending = <Absent>loading</Absent>
  const failed = <Absent>the API did not answer</Absent>

  function figure(query: { isPending: boolean; isError: boolean }, value: () => string) {
    if (query.isPending) return pending
    if (query.isError) return failed
    return value()
  }

  return (
    <KpiStrip
      items={[
        {
          label: "Findings recorded",
          value: figure(findings, () => findings.data!.total.toLocaleString()),
          note: "everything DETECT has produced, including findings since closed",
          figure: findings.isSuccess,
        },
        {
          label: "Still open",
          value: figure(findings, () => findings.data!.still_open.toLocaleString()),
          note: "of those, how many remain — the series above does not shrink as these close",
          figure: findings.isSuccess,
        },
        {
          label: "Changes published",
          value: figure(changes, () => changes.data!.total.toLocaleString()),
          // Not comparable with the findings count, and the note says which direction the
          // difference runs: most of what a vendor publishes touches nothing here.
          note: "by the watched integrations, fleet-wide — most touch nothing this codebase calls",
          figure: changes.isSuccess,
        },
        {
          label: "Days with activity",
          // Both queries, because the set below unions both. Gated on `changes` alone this
          // returned a day count computed from an empty findings array while findings was still
          // pending -- a number from half the data, under a label the status band renders from
          // all of it, on the same screen.
          value: figure(
            {
              isPending: changes.isPending || findings.isPending,
              isError: changes.isError || findings.isError,
            },
            () => {
            const days = new Set([
              ...(findings.data?.days ?? []).map((d) => d.day),
              ...(changes.data?.days ?? []).map((d) => d.day),
            ])
              return days.size.toLocaleString()
            }
          ),
          // A count of days that *have* a row, never a span: a day with no row is a day nothing
          // was recorded, which may be a day nothing happened or a day nothing ran.
          note: "days either series recorded something — not the length of the window",
          figure: changes.isSuccess && findings.isSuccess,
        },
      ]}
    />
  )
}
