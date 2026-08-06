/**
 * Narrowing a table that is too long to read.
 *
 * Both controls here send the narrowing to the API rather than applying it to the rows already
 * on screen. A filter applied to the current page reports a total drawn from the set it never
 * filtered, which is the "a reader cannot tell what this view can see" defect this console has
 * closed six times — it would come straight back as an affordance.
 *
 * Neither control animates. A filter is a frequent interaction, and a delay an operator pays on
 * every click is a cost with no information behind it; the state change is the answer arriving,
 * which the table already shows.
 *
 * No icons either. An icon is a label, not a distinction the graph holds, and the words fit.
 */

import { useState, type FormEvent, type ReactNode } from "react"

import { Button } from "@/components/ui/button"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group"

/** One option a facet offers, with how many rows it accounts for. */
export interface FacetOption {
  value: string
  /** How many rows carry this value, counted over the facet's own scope — never the page. */
  count: number
}

/**
 * Selected and unselected, as named surface steps.
 *
 * The catalog's own `outline`/`secondary` pairing renders this backwards here: `outline` fills
 * with `input/30`, a translucent light wash, while `secondary` is `0.255` — flat and *darker*
 * than the wash. Measured on the running screen, the unselected chips came back brighter than
 * the selected one, which is the state distinction inverted rather than merely subtle.
 *
 * So the steps are named instead, which is what `DESIGN.md`'s surface ramp reserves them for: a
 * control at rest takes its panel's own depth step, `surface-emphasis` is a selection, and
 * `surface-subtle` is the pointer. Rest, hover and selected then climb the ramp in that order.
 * The `dark:` spellings are the ones that land — the console is dark-only and the class is
 * permanent — but both are written so the override does not depend on which variant the
 * catalog happens to use for a background.
 */
function chipSurface(selected: boolean): string {
  return selected
    ? "border-line-strong bg-surface-emphasis hover:bg-surface-emphasis dark:border-line-strong dark:bg-surface-emphasis dark:hover:bg-surface-emphasis"
    : "border-line bg-surface hover:bg-surface-subtle dark:border-line dark:bg-surface dark:hover:bg-surface-subtle"
}

/**
 * A closed set of values a column takes, each with its count, one selectable at a time.
 *
 * Chips rather than a dropdown because the counts are the point: an operator choosing between
 * `breaking` and `warning` is choosing between forty rows and three, and a dropdown hides that
 * until after the choice. The trade is that this only works while the set is small, which is a
 * property of the columns it is used on rather than a hope — a severity has five possible
 * values and an operation is called from as many repositories as a customer has.
 *
 * `countScope` states what the counts are counted over, because they are deliberately not
 * counted over the filtered page: an option list narrowed by the filter it sets collapses to
 * whatever is already selected and leaves no way back to the rest. So the numbers on the chips
 * and the number under the table are answers to two different questions, and the reader is told
 * which is which rather than left to assume they agree.
 *
 * Selection is carried by `aria-pressed` as well as by the surface step, so the state is
 * readable without colour. The colour here claims a selection, not a verdict — nothing on these
 * chips grades anything, and a severity's own hue is deliberately absent for that reason.
 */
export function FacetChips({
  legend,
  options,
  selected,
  onSelect,
  allLabel,
  countScope,
}: {
  legend: string
  options: FacetOption[]
  selected: string | null
  onSelect: (value: string | null) => void
  /** What the unfiltered chip says, in this column's own words. */
  allLabel: string
  countScope: string
}) {
  if (options.length === 0) return null

  return (
    <fieldset className="flex min-w-0 flex-1 flex-col gap-row">
      <legend className="furniture text-meta text-ink-muted">{legend}</legend>
      <div className="flex flex-wrap items-center gap-row">
        <Button
          type="button"
          size="sm"
          variant="outline"
          className={chipSurface(selected === null)}
          aria-pressed={selected === null}
          onClick={() => onSelect(null)}
        >
          {allLabel}
        </Button>
        {options.map((option) => (
          <Button
            key={option.value}
            type="button"
            size="sm"
            variant="outline"
            className={chipSurface(selected === option.value)}
            aria-pressed={selected === option.value}
            onClick={() => onSelect(selected === option.value ? null : option.value)}
          >
            <span className="font-mono">{option.value}</span>
            <span className="text-ink-muted">{option.count.toLocaleString()}</span>
          </Button>
        ))}
      </div>
      <p className="max-w-prose text-meta text-muted-foreground">{countScope}</p>
    </fieldset>
  )
}

/**
 * A path prefix, applied on submit rather than on every keystroke.
 *
 * No debounce, and that is the design rather than an omission. A debounce is a guess at when
 * somebody has stopped typing, and every guess it gets wrong is either a request nobody wanted
 * or a wait nobody asked for; an explicit submit is one request for one intention. It also
 * means the URL — which is what makes a narrowed table shareable — only ever holds a filter the
 * operator finished writing.
 *
 * The input is keyed on the committed value so an external change to it (the clear control, a
 * pasted URL, browser Back) replaces the draft rather than leaving a stale one in the box. The
 * URL is the source of truth; what is typed is a draft until submitted.
 */
export function PrefixFilter({
  legend,
  value,
  onSubmit,
  placeholder,
  note,
}: {
  legend: string
  value: string | null
  onSubmit: (next: string | null) => void
  placeholder: string
  note: string
}) {
  return (
    <PrefixFilterForm
      key={value ?? ""}
      legend={legend}
      value={value}
      onSubmit={onSubmit}
      placeholder={placeholder}
      note={note}
    />
  )
}

function PrefixFilterForm({
  legend,
  value,
  onSubmit,
  placeholder,
  note,
}: {
  legend: string
  value: string | null
  onSubmit: (next: string | null) => void
  placeholder: string
  note: string
}) {
  const [draft, setDraft] = useState(value ?? "")

  function submit(event: FormEvent) {
    event.preventDefault()
    const trimmed = draft.trim()
    onSubmit(trimmed === "" ? null : trimmed)
  }

  return (
    <form className="flex min-w-0 flex-1 flex-col gap-row" onSubmit={submit}>
      <label className="furniture text-meta text-ink-muted" htmlFor={`${legend}-prefix`}>
        {legend}
      </label>
      <InputGroup className="max-w-prose">
        <InputGroupInput
          id={`${legend}-prefix`}
          className="font-mono"
          value={draft}
          placeholder={placeholder}
          onChange={(event) => setDraft(event.target.value)}
        />
        <InputGroupAddon align="inline-end">
          <InputGroupButton type="submit">Filter</InputGroupButton>
          {value !== null && (
            <InputGroupButton type="button" onClick={() => onSubmit(null)}>
              Clear
            </InputGroupButton>
          )}
        </InputGroupAddon>
      </InputGroup>
      <p className="max-w-prose text-meta text-muted-foreground">{note}</p>
    </form>
  )
}

/**
 * What is currently narrowing a table, said in words, with one control to undo all of it.
 *
 * This exists because a filter left on is invisible from the rows: an operator returning to a
 * tab, or opening a link somebody sent, sees a short table and no reason for it. Stating the
 * filters in prose rather than only as a selected chip is what makes a narrowed view legible as
 * narrow, which is the whole precondition for reading its emptiness correctly.
 */
/**
 * The controls that narrow one table, laid out together above it.
 *
 * A row rather than a stack because the table is what the screen is for: two stacked controls
 * with an explanatory sentence each cost a quarter of the viewport before the first row of
 * data. It wraps rather than shrinking, so a narrow window gets the stack back instead of two
 * controls too small to use.
 */
export function FilterBar({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap items-start gap-section">{children}</div>
}

export function ActiveFilters({
  filters,
  onClear,
}: {
  filters: { label: string; value: string }[]
  onClear: () => void
}) {
  if (filters.length === 0) return null

  return (
    <div className="flex flex-wrap items-center gap-row text-body">
      <span className="text-ink-muted">Narrowed by</span>
      {filters.map((filter) => (
        <span key={filter.label} className="text-ink-secondary">
          {filter.label} <span className="font-mono">{filter.value}</span>
        </span>
      ))}
      <Button type="button" size="sm" variant="outline" onClick={onClear}>
        Clear all filters
      </Button>
    </div>
  )
}
