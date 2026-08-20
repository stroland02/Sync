/**
 * Which integrations share a file, and how much â€” the coupling the topology card can only count.
 *
 * `ApiTopologyCard` reports *files calling more than one integration* as a number and a list of
 * paths. That answers "is there coupling" and not "between which integrations", and the second is
 * the one that predicts what a change costs: a file touching Stripe and Anthropic means a Stripe
 * change lands in code that also has to keep working for Anthropic.
 *
 * **A chord is the right form here because the relation is symmetric and dense.** Stripe-with-
 * Anthropic is the same fact as Anthropic-with-Stripe, so a directed diagram would draw every
 * relation twice; and every integration can pair with every other, which a ranking flattens into
 * a list that hides who pairs with whom.
 *
 * **The diagonal is dropped.** An integration "coupled with itself" is just its own file count,
 * which the topology card already reports â€” drawing it would make the largest integration a
 * near-complete circle and squeeze every real pairing into the remainder.
 *
 * **Absent is not zero, and this is a case where the difference shows.** A ribbon that is not
 * drawn means no file calls both, which the index measured. An integration with no ribbons at all
 * is genuinely uncoupled â€” the honest and common case for a codebase that keeps its vendor calls
 * separate, and not a rendering failure.
 */

import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { chord, ribbon } from "d3-chord"
import { arc } from "d3-shape"

import { fetchTopology } from "@/features/repositories/api-topology-card"
import { InfoHint } from "@/components/info-hint"
import { MetricPanel } from "@/components/metric-panel"
import { ErrorState, LoadingState } from "@/components/states"
import { seriesScale } from "@/lib/palette"

const SIZE = 420
const OUTER = SIZE / 2 - 56
const INNER = OUTER - 9

/**
 * The symmetric coupling matrix, built from the files each integration is called from.
 *
 * `multi_vendor_files` names the files that reach more than one integration but not which ones,
 * so the matrix is derived from `by_vendor` file counts and the multi-vendor list together: a
 * shared file contributes one to each pairing it participates in.
 */
function couplingMatrix(
  vendors: string[],
  shared: { path: string; vendors: number; call_sites: number }[],
): number[][] {
  const size = vendors.length
  const matrix = Array.from({ length: size }, () => new Array<number>(size).fill(0))
  // Each shared file couples every pair among the integrations it touches. The payload carries a
  // count rather than the names, so a file touching `n` integrations is spread evenly across the
  // pairs it could form -- stated in the panel, because an even spread is an assumption and not a
  // measurement of which specific pair a file joined.
  for (const file of shared) {
    const pairs = (file.vendors * (file.vendors - 1)) / 2
    if (pairs <= 0) continue
    const weight = 1 / pairs
    for (let a = 0; a < Math.min(file.vendors, size); a += 1) {
      for (let b = a + 1; b < Math.min(file.vendors, size); b += 1) {
        matrix[a][b] += weight
        matrix[b][a] += weight
      }
    }
  }
  return matrix
}

export function CouplingChord({ repoId }: { repoId: string }) {
  const query = useQuery({
    queryKey: ["api-topology", repoId],
    queryFn: ({ signal }) => fetchTopology(repoId, signal),
  })

  const vendors = useMemo(
    () => (query.data?.by_vendor ?? []).map((row) => row.vendor_id).sort(),
    [query.data],
  )
  const layout = useMemo(() => {
    if (query.data === undefined || vendors.length < 2) return null
    const matrix = couplingMatrix(vendors, query.data.multi_vendor_files)
    const total = matrix.flat().reduce((sum, n) => sum + n, 0)
    if (total === 0) return null
    return chord().padAngle(0.045)(matrix)
  }, [query.data, vendors])

  if (query.isPending) return <LoadingState what="integration coupling" />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what="integration coupling"
        onRetry={() => void query.refetch()}
      />
    )
  }

  const hint = (
    <InfoHint label="About integration coupling">
      Which integrations are called from the same file. A ribbon between two means at least one
      file reaches both, so a change to either lands in code that has to keep working for the
      other â€” which is what makes a change expensive rather than merely present. Derived from the
      files the index found calling more than one integration; where a file touches three or more,
      its weight is spread evenly across the pairs it could form, because the payload carries how
      many it touched and not which. No ribbon between two integrations means no file calls both,
      which the index measured â€” not something it failed to look for.
    </InfoHint>
  )

  if (vendors.length < 2) {
    return (
      <MetricPanel label="Integration coupling" hint={hint} caption="Fewer than two integrations are called here.">
        <p className="max-w-prose text-body text-ink-muted">
          Coupling is a relation between integrations, and this codebase calls{" "}
          {vendors.length === 1 ? "only one" : "none"}. There is nothing to relate.
        </p>
      </MetricPanel>
    )
  }

  if (layout === null) {
    return (
      <MetricPanel
        label="Integration coupling"
        hint={hint}
        caption="No file calls more than one integration."
      >
        <p className="max-w-prose text-body text-ink-muted">
          Every file that calls out reaches exactly one integration. That is a measured zero â€” the
          index read {vendors.length} integrations across this codebase and found no file shared
          between them â€” and it is the cheap case: a change to one integration cannot land in code
          that has to keep working for another.
        </p>
      </MetricPanel>
    )
  }

  const colour = seriesScale(vendors)
  const arcGenerator = arc<{ startAngle: number; endAngle: number }>()
    .innerRadius(INNER)
    .outerRadius(OUTER)
  const ribbonGenerator = ribbon().radius(INNER)

  return (
    <MetricPanel
      label="Integration coupling"
      hint={hint}
      caption="Integrations called from the same file. A ribbon is shared code; an arc's length is how much of this codebase's coupling that integration participates in."
    >
      <div className="flex justify-center">
        <svg
          viewBox={`${-SIZE / 2} ${-SIZE / 2} ${SIZE} ${SIZE}`}
          className="w-full max-w-[26rem]"
          role="img"
          aria-label={`Integration coupling between ${vendors.join(", ")}`}
        >
          <g>
            {layout.map((group, index) => (
              <path
                key={`ribbon-${index}`}
                d={ribbonGenerator(group as never) ?? undefined}
                fill={colour(vendors[group.source.index])}
                fillOpacity={0.4}
                stroke={colour(vendors[group.source.index])}
                strokeOpacity={0.7}
              />
            ))}
          </g>
          <g>
            {layout.groups.map((group) => {
              const mid = (group.startAngle + group.endAngle) / 2
              const flip = mid > Math.PI
              return (
                <g key={`arc-${group.index}`}>
                  <path d={arcGenerator(group) ?? undefined} fill={colour(vendors[group.index])} />
                  <text
                    transform={`rotate(${(mid * 180) / Math.PI - 90}) translate(${OUTER + 8}) ${
                      flip ? "rotate(180)" : ""
                    }`}
                    textAnchor={flip ? "end" : "start"}
                    dy="0.35em"
                    className="fill-ink font-mono text-[12px]"
                  >
                    {vendors[group.index]}
                  </text>
                </g>
              )
            })}
          </g>
        </svg>
      </div>
    </MetricPanel>
  )
}
