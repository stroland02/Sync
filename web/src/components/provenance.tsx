/**
 * Where the answer came from, rendered beside the answer.
 *
 * The rung is a column in the database rather than a nicety because a false positive that
 * cannot be attributed to a rung cannot be fixed. Hiding it here would throw away the
 * property that makes the payload worth trusting.
 *
 * Two levels, deliberately not merged. The per-row rung on a finding is the rung of that
 * finding. The envelope's rung describes the whole page and goes null whenever the page
 * rests on no single binding — which means something different on each route, so
 * `bindingNullLabel` is required rather than defaulted.
 */

import type { ReactNode } from "react"

import type { BindingSource, Provenance } from "@/api/types"
import { Absent, Formatted } from "@/components/status"
import { describeRung, formatTimestamp } from "@/lib/format"

/**
 * The rung of one binding. Never null at this level — a finding always carries one.
 *
 * The rung records how a binding was established (static / resolved / observed / …), not
 * how much to trust it. Colouring it would restate the scalar confidence score this project
 * rejected twice, so it takes the design system's weight and spacing and never its hue.
 */
export function RungBadge({ rung }: { rung: BindingSource }) {
  return (
    <span
      className="furniture rounded-control border border-line px-field py-0.5 font-mono text-meta"
      title={describeRung(rung)}
    >
      {rung}
    </span>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="furniture text-meta text-ink-muted">{label}</dt>
      <dd className="font-mono text-meta">{children}</dd>
    </div>
  )
}

export function ProvenanceStrip({
  provenance,
  bindingNullLabel,
  indexedNullLabel = "not recorded",
}: {
  provenance: Provenance
  /** What a null envelope rung means *here*. Required: null is a fact, and it differs per route. */
  bindingNullLabel: string
  /** What a null `indexed_at` means here. Defaults to the honest generic. */
  indexedNullLabel?: string
}) {
  const { indexed_at, feed_fetched_at, binding_source, context_savings, context_savings_bound_reached } =
    provenance
  return (
    <div className="flex flex-col gap-2 border-t border-border pt-3">
      <dl className="flex flex-wrap gap-x-8 gap-y-3">
        <Field label="Binding source">
          {binding_source === null ? (
            <Absent>{bindingNullLabel}</Absent>
          ) : (
            <span title={describeRung(binding_source)}>{binding_source}</span>
          )}
        </Field>
        <Field label="Indexed at">
          {indexed_at === null ? (
            <Absent>{indexedNullLabel}</Absent>
          ) : (
            <time dateTime={indexed_at}>
              <Formatted value={formatTimestamp(indexed_at)} />
            </time>
          )}
        </Field>
        <Field label="Feed fetched at">
          {feed_fetched_at === null ? (
            <Absent>no feed recorded</Absent>
          ) : (
            <time dateTime={feed_fetched_at}>
              <Formatted value={formatTimestamp(feed_fetched_at)} />
            </time>
          )}
        </Field>
        {/* `+` mirrors `describeBoundedTotal` (`features/fleet/cardinality.tsx`) rather than
            importing it: that module is fleet-scoped and this strip is not, and the format is a
            two-token ternary, cheap enough to restate exactly rather than pull a feature into a
            shared component's dependency graph for it. Wording, not the fact, is what may vary --
            see that module's own docstring for the vocabulary this must not drift from. */}
        <Field label="Context savings">
          {context_savings_bound_reached
            ? `${context_savings.toLocaleString()}+ tokens`
            : `${context_savings.toLocaleString()} tokens`}
        </Field>
      </dl>
      {context_savings_bound_reached && (
        <p className="max-w-prose text-body text-muted-foreground">
          This figure is a floor, not the true savings: it is derived from a count that stopped
          early, and it does not say how much more the graph would save if that count had kept
          going.
        </p>
      )}
    </div>
  )
}
