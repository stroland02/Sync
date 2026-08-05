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
import { ABSENT, describeRung, formatTimestamp } from "@/lib/format"

/** The rung of one binding. Never null at this level — a finding always carries one. */
export function RungBadge({ rung }: { rung: BindingSource }) {
  return (
    <span
      className="rounded border border-border px-1.5 py-0.5 font-mono text-xs"
      title={describeRung(rung)}
    >
      {rung}
    </span>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs tracking-wide text-muted-foreground uppercase">{label}</dt>
      <dd className="font-mono text-xs">{children}</dd>
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
  const { indexed_at, feed_fetched_at, binding_source, context_savings } = provenance
  return (
    <dl className="flex flex-wrap gap-x-8 gap-y-3 border-t border-border pt-3">
      <Field label="Binding source">
        {binding_source === null ? (
          <span className="text-muted-foreground">
            {ABSENT} {bindingNullLabel}
          </span>
        ) : (
          <span title={describeRung(binding_source)}>{binding_source}</span>
        )}
      </Field>
      <Field label="Indexed at">
        {indexed_at === null ? (
          <span className="text-muted-foreground">
            {ABSENT} {indexedNullLabel}
          </span>
        ) : (
          <time dateTime={indexed_at}>{formatTimestamp(indexed_at)}</time>
        )}
      </Field>
      <Field label="Feed fetched at">
        {feed_fetched_at === null ? (
          <span className="text-muted-foreground">{ABSENT} no feed recorded</span>
        ) : (
          <time dateTime={feed_fetched_at}>{formatTimestamp(feed_fetched_at)}</time>
        )}
      </Field>
      <Field label="Context savings">{`${context_savings.toLocaleString()} tokens`}</Field>
    </dl>
  )
}
