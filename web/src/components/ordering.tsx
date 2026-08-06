/**
 * Choosing how a long table is arranged, and saying which arrangement is on screen.
 *
 * Separate from `filters.tsx` on purpose. A filter changes which rows exist and the total under
 * the table moves with it; an ordering changes nothing about the set and the total is the same
 * number either way. Conflating the two is how a sort ends up reported as a filter — or worse,
 * applied to the fifty rows already fetched and presented as the worst fifty of two and a half
 * thousand, which is the "a reader cannot tell what this view can see" defect this console has
 * closed six times. Every ordering here is a SQL `ORDER BY` ahead of the page's own `LIMIT`.
 *
 * **The sentence is the load-bearing part, not the buttons.** A table that has never been sorted
 * is not unsorted — it is in the order Sync raised the findings, and before this it said so
 * nowhere. A reader who cannot see the ordering cannot tell a page boundary that moved from a
 * finding that changed, so this states the applied ordering whether or not anybody chose one.
 *
 * The applied ordering comes from the payload rather than from the URL. An unrecognised `order`
 * resolves server-side and the envelope reports what was used, so there is no version of this
 * where the control names one arrangement and the rows are in another.
 *
 * No animation. Re-ordering a table is a frequent interaction and the answer arriving is the
 * feedback; a transition would be a delay paid on every click with no information behind it.
 *
 * The selected-state surface is shared with the filter chips through `lib/selectable-surface`, and
 * that is the only thing the two share: one arrangement of the surface ramp, in one place, so the
 * same three steps cannot drift into two meanings.
 */

import type { FindingOrder } from "@/api/types"
import { Button } from "@/components/ui/button"
import { chipSurface } from "@/lib/selectable-surface"

/** One ordering, in the operator's words rather than the column's. */
interface OrderOption {
  value: FindingOrder
  /** What the button says. */
  label: string
}

/**
 * Two orderings, and no more without an argument.
 *
 * A control offering to sort by every column is the component catalogue talking: `binding_rung` is
 * an evidence class with no good end, so ranking it would smuggle back the confidence score this
 * project has refused twice, and ordering by a path sorts a codebase alphabetically and calls it a
 * priority. These two are the orderings that answer a question an operator actually arrives with —
 * *what is the worst thing here*, and *what did Sync find first*.
 */
const ORDERS: OrderOption[] = [
  { value: "first-seen", label: "As Sync found them" },
  { value: "severity", label: "Most severe first" },
]

/**
 * What the current arrangement is, in one sentence, for a reader who chose nothing.
 *
 * The severity sentence names the whole ranking, because the ranking is a **declared judgement and
 * not a fact the graph stores** — `Severity` is a closed vocabulary with no order stored anywhere,
 * so ordering by it means inventing a rank, and an invented rank that a reader cannot see is one
 * nobody can disagree with. The rank arrives in the payload, so what is printed here is the order
 * the query actually used.
 */
function orderingSentence(order: FindingOrder, severityOrder: string[]): string {
  if (order === "severity") {
    return (
      `Ordered by severity, most severe first: ${severityOrder.join(" → ")}. ` +
      "That ranking is Sync's own — severity is a closed vocabulary with no order stored " +
      "anywhere in the graph, so this one is declared rather than measured. Findings of one " +
      "severity stay in the order Sync found them."
    )
  }
  return (
    "Ordered as Sync found them — the oldest open finding first. Nothing here is ranked by " +
    "severity until you ask for it, so the first row is the longest-standing finding rather " +
    "than the worst one."
  )
}

/**
 * `applied` is the ordering the query used, read off the payload — deliberately not the value in
 * the URL. The two differ only when a URL names an ordering the API does not have, and the pressed
 * state follows the payload because a button reflecting the URL would show a choice the rows do not
 * honour. There is no `selected` prop for that reason: the URL is a request, not a state.
 *
 * Selection is carried by `aria-pressed` as well as by the surface step, so which ordering is on is
 * readable without colour — and the sentence below states it in words regardless.
 */
export function OrderChoice({
  legend,
  applied,
  severityOrder,
  onSelect,
}: {
  legend: string
  applied: FindingOrder
  severityOrder: string[]
  onSelect: (value: FindingOrder) => void
}) {
  return (
    <fieldset className="flex min-w-0 flex-1 flex-col gap-row">
      <legend className="furniture text-meta text-ink-muted">{legend}</legend>
      <div className="flex flex-wrap items-center gap-row">
        {ORDERS.map((option) => (
          <Button
            key={option.value}
            type="button"
            size="sm"
            variant="outline"
            className={chipSurface(applied === option.value)}
            aria-pressed={applied === option.value}
            onClick={() => onSelect(option.value)}
          >
            {option.label}
          </Button>
        ))}
      </div>
      <p className="max-w-prose text-meta text-muted-foreground">
        {orderingSentence(applied, severityOrder)}
      </p>
    </fieldset>
  )
}
