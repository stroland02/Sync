/**
 * A left rail that narrows a set too large to read, with a count beside every option.
 *
 * The arrangement is a convention of the form — `.claude/rules/interface-originality.md` permits
 * a filter rail the way it permits a table. **What is ours is the count.**
 * `docs/superpowers/plans/2026-08-18-page-information-architecture.md:150-152` puts the entire
 * value of this surface there: the counts *"tell you what you would get before you click"*. That
 * only holds if a count is honest about what class of answer it is, so the type carries the
 * distinction rather than the caller's discipline carrying it.
 *
 * **A confirmed zero and an unanswered count are different facts and there is no `number` to
 * pass.** A count is `{ kind: "counted", value }` or `{ kind: "unanswered", why }`. A view that
 * never asked the question cannot render `0` by accident; it renders the console's one absence
 * marker, and the reason travels with it — on the option for a screen reader, and in the rail's
 * own note for everyone else. An absence marker with no reason behind it is the defect this
 * console has closed repeatedly: "we did not ask", "the route failed" and "this view cannot see
 * it" all arrive as one glyph otherwise.
 *
 * **An option counted at zero stays selectable.** It is a real answer — the filter would return
 * nothing — and that is worth clicking to establish. Disabling it, or dropping it from the list,
 * makes the rail assert the value does not exist in the vocabulary, which is a different claim
 * and a false one.
 *
 * **What this component refuses to render**, each because the data does not hold it:
 *
 * - **No total, over a group or over the rail.** Every figure on screen is one the caller was
 *   given. A sum over a set where one member is unanswered is not a number anybody measured, and
 *   a sum over a set where none is would still be this component inventing a figure. The
 *   unfiltered option's count is supplied by the caller for exactly that reason.
 * - **No colour grading an option.** Selection is carried by `aria-pressed` and by a named
 *   surface step, both legible without hue. A count tinted by how large it is would be a severity
 *   this console did not measure.
 * - **No dot, badge tone, bar or histogram.** The timeline histogram the reference rail carries
 *   above its table is a separate surface with its own dependency question, and is not here.
 *
 * `FilterCount` is `TriageCount` under another name rather than a second declaration of the same
 * shape. Two spellings of "counted or unanswered" would drift, and the drift would be silent —
 * which is the expensive kind. The type wants a home neither component owns; see this file's
 * deferred-work note in the task report.
 */

import { useId, useState } from "react"

import { Absent, Formatted } from "@/components/status"
import { Button } from "@/components/ui/button"
import type { TriageCount } from "@/components/triage-tabs"
import { chipSurface } from "@/lib/selectable-surface"

/**
 * How many records an option accounts for — or that nobody answered the question.
 *
 * `why` is required on the unanswered arm, and it is the sentence a reader gets instead of a
 * figure. There is no arm that carries absence without a reason.
 */
export type FilterCount = TriageCount

/** One value a facet takes, and what it accounts for. */
export interface FilterOption {
  /** The vocabulary value itself, as the filter would send it. */
  readonly value: string
  /** How that value is written for a reader. */
  readonly label: string
  readonly count: FilterCount
}

/**
 * One facet of the rail: a legend, a closed set of values, and which one is narrowing the set.
 *
 * `options` is a non-empty tuple. Every facet this rail serves is a closed vocabulary known
 * before the query runs — a time range, a change kind, a run outcome — so an empty list is not
 * "this facet has no values", it is a caller that has not got its vocabulary yet. Making that
 * uncompilable is cheaper than rendering a blank fieldset that reads as an answer.
 */
export interface FilterGroup {
  readonly id: string
  /** What the facet divides, in this facet's own words — "Time range", "Level". */
  readonly legend: string
  readonly options: readonly [FilterOption, ...FilterOption[]]
  /**
   * The values currently narrowing the set. Empty is the whole set.
   *
   * **A set rather than one value, as of M15 Task 4.** A codebase with forty integrations is not
   * filterable one at a time: the pair a reader wants -- two integrations, or the severities that
   * are not `info` -- had no sequence of presses that reached it. Several values are a union, and
   * the count beside each option still ignores that option's own facet.
   */
  readonly selected: readonly string[]
  /**
   * Toggles one value in or out; `null` clears the facet.
   *
   * The rail never holds selection state of its own -- what is pressed is what the caller was
   * handed, so a URL a reader pasted and the rail they are looking at cannot disagree.
   */
  readonly onSelect: (value: string | null) => void
  /**
   * The unfiltered option, when the caller holds an honest count for the whole facet.
   *
   * Optional because that count is a total, and nothing here may compute one. A caller without
   * it omits this and the facet clears by picking its selected option again.
   */
  readonly unfiltered?: { readonly label: string; readonly count: FilterCount }
}

/** An option whose count nobody answered, named well enough to act on. */
export interface UnansweredCount {
  readonly legend: string
  readonly label: string
  readonly why: string
}

/** What is narrowing a facet: one of its own values, or something its vocabulary does not hold. */
export type ActiveSelection =
  | {
      readonly kind: "option"
      readonly legend: string
      readonly value: string
      readonly label: string
    }
  | { readonly kind: "outside-vocabulary"; readonly legend: string; readonly value: string }

/**
 * The count as text, or `null` for absence — never a glyph, per `@/lib/format`'s contract.
 *
 * Exported because the mapping from an unanswered count to absence is the one derivation on this
 * surface with a wrong answer, and `.claude/rules/console-dev-loop.md` puts those under test.
 */
export function formatFilterCount(count: FilterCount): string | null {
  return count.kind === "counted" ? count.value.toLocaleString() : null
}

/**
 * Every count on the rail nobody answered, in the order they appear.
 *
 * This is what the rail's note is built from. A rail carrying absence markers and no explanation
 * would be telling a reader that some options return nothing, which is the opposite of what an
 * unanswered count means.
 */
export function unansweredCounts(groups: readonly FilterGroup[]): UnansweredCount[] {
  const unanswered: UnansweredCount[] = []
  for (const group of groups) {
    const counts: { label: string; count: FilterCount }[] = [
      ...(group.unfiltered ? [{ label: group.unfiltered.label, count: group.unfiltered.count }] : []),
      ...group.options.map((option) => ({ label: option.label, count: option.count })),
    ]
    for (const entry of counts) {
      if (entry.count.kind === "unanswered") {
        unanswered.push({ legend: group.legend, label: entry.label, why: entry.count.why })
      }
    }
  }
  return unanswered
}

/**
 * What each narrowed facet is narrowed by.
 *
 * A selection its own group does not hold — a stale URL parameter, a value retired from the
 * vocabulary — is reported rather than dropped. Dropping it leaves a rail with nothing pressed
 * over a table that is nonetheless narrowed, which is the "a reader cannot tell what this view
 * can see" failure in its purest form.
 */
export function activeSelections(groups: readonly FilterGroup[]): ActiveSelection[] {
  const selections: ActiveSelection[] = []
  for (const group of groups) {
    for (const selected of group.selected) {
      const option = group.options.find((candidate) => candidate.value === selected)
      selections.push(
        option === undefined
          ? { kind: "outside-vocabulary", legend: group.legend, value: selected }
          : {
              kind: "option",
              legend: group.legend,
              value: option.value,
              label: option.label,
            }
      )
    }
  }
  return selections
}

/**
 * Above how many options a facet offers a search box.
 *
 * A search box over four options is furniture that costs a reader a decision and returns
 * nothing; over forty it is the only way to reach the one they want. The threshold is a
 * judgement rather than a measurement, and it is here as a named constant so it is one
 * judgement rather than one per screen.
 */
export const SEARCHABLE_ABOVE = 8

/**
 * The options a search term admits, matched on the value as well as the label.
 *
 * Both, because a reader searching a facet of vendor identifiers types what they saw in a URL or
 * a stack trace, which is the value; a reader searching operations types the prose. Matching one
 * would silently hide the rows the other was looking for.
 *
 * **A selected option always survives the search.** Otherwise typing into the box hides an option
 * that is currently narrowing the table, and the only control that would clear it is the one that
 * just disappeared -- a reader would be left with a filtered table and an apparently empty facet.
 */
export function matchingOptions(
  options: readonly FilterOption[],
  query: string,
  selected: readonly string[] = [],
): FilterOption[] {
  const term = query.trim().toLowerCase()
  if (term === "") return [...options]
  return options.filter(
    (option) =>
      selected.includes(option.value) ||
      option.label.toLowerCase().includes(term) ||
      option.value.toLowerCase().includes(term)
  )
}

function OptionCount({ count }: { count: FilterCount }) {
  return (
    <span className="text-ink-muted tabular-nums">
      <Formatted value={formatFilterCount(count)} />
      {count.kind === "unanswered" && (
        <span className="sr-only"> count not answered: {count.why}</span>
      )}
    </span>
  )
}

function OptionButton({
  label,
  count,
  pressed,
  onClick,
}: {
  label: string
  count: FilterCount
  pressed: boolean
  onClick: () => void
}) {
  return (
    <Button
      type="button"
      size="sm"
      variant="outline"
      // Never `disabled`, whatever the count says. A zero here is an answer worth selecting.
      className={`w-full justify-between ${chipSurface(pressed)}`}
      aria-pressed={pressed}
      onClick={onClick}
    >
      <span className="min-w-0 truncate">{label}</span>
      <OptionCount count={count} />
    </Button>
  )
}

function Group({ group }: { group: FilterGroup }) {
  const [query, setQuery] = useState("")
  const searchId = useId()
  const searchable = group.options.length > SEARCHABLE_ABOVE
  const shown = searchable ? matchingOptions(group.options, query, group.selected) : group.options
  const stray = activeSelections([group]).filter(
    (selection) => selection.kind === "outside-vocabulary"
  )

  return (
    <fieldset className="flex min-w-0 flex-col gap-row">
      <legend className="furniture text-meta text-ink-muted">{group.legend}</legend>
      {searchable && (
        <>
          <label htmlFor={searchId} className="sr-only">
            Search {group.legend.toLowerCase()}
          </label>
          <input
            id={searchId}
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={`Search ${group.options.length} values`}
            className="w-full rounded-control border border-line bg-surface-subtle px-field py-field text-meta text-ink placeholder:text-ink-muted focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </>
      )}
      <div className="flex min-w-0 flex-col gap-field">
        {group.unfiltered !== undefined && (
          <OptionButton
            label={group.unfiltered.label}
            count={group.unfiltered.count}
            // Pressed when nothing narrows the facet, which under a set is an empty one.
            pressed={group.selected.length === 0}
            onClick={() => group.onSelect(null)}
          />
        )}
        {shown.map((option) => (
          <OptionButton
            key={option.value}
            label={option.label}
            count={option.count}
            pressed={group.selected.includes(option.value)}
            // A press toggles this value alone and the others stand. Pressing a pressed option
            // removes it, which is how a reader gets back without reaching for the clear.
            onClick={() => group.onSelect(option.value)}
          />
        ))}
        {searchable && shown.length === 0 && (
          <p className="text-meta text-ink-muted">
            No value in this facet matches <span className="font-mono text-ink">{query}</span>.
            The facet holds {group.options.length.toLocaleString()}.
          </p>
        )}
      </div>
      {stray.map((selection) => (
        <p key={selection.value} className="max-w-prose text-meta text-ink-muted">
          Narrowed by <span className="font-mono text-ink">{selection.value}</span>, which is not
          one of this facet&rsquo;s values — nothing above is selected for it because nothing
          above matches it, and the counts beside these options do not describe the set on screen.
        </p>
      ))}
    </fieldset>
  )
}

/**
 * The rail itself. Stateless: every selection is the caller's, sent to the API rather than
 * applied to the rows already on screen — a filter applied to the current page reports a total
 * drawn from the set it never filtered.
 */
export function FilterRail({
  label,
  groups,
  countScope,
}: {
  /** What the rail narrows, named for a reader and for a screen reader. */
  label: string
  groups: readonly [FilterGroup, ...FilterGroup[]]
  /**
   * What the counts are counted over, in words. Required.
   *
   * They are deliberately not counted over the filtered page: an option list narrowed by the
   * filter it sets collapses to whatever is already selected and leaves no way back to the rest.
   * So the figures here and the figure under the table answer two different questions, and the
   * reader is told which is which rather than left to assume they agree.
   */
  countScope: string
}) {
  const headingId = useId()
  const unanswered = unansweredCounts(groups)

  return (
    <aside
      aria-labelledby={headingId}
      className="flex min-w-0 flex-col gap-section self-stretch overflow-y-auto rounded-surface border border-line bg-surface p-section lg:sticky lg:top-frame lg:max-h-[calc(100svh-8rem)]"
    >
      <h2 id={headingId} className="furniture text-meta text-ink">
        {label}
      </h2>
      {groups.map((group) => (
        <Group key={group.id} group={group} />
      ))}
      <div className="flex flex-col gap-field">
        <p className="max-w-prose text-meta text-ink-muted">{countScope}</p>
        {unanswered.length > 0 && (
          <div className="flex flex-col gap-field text-meta text-ink-muted">
            <p className="max-w-prose">
              <Absent>is not a zero</Absent>. These counts were not answered, so the rail cannot
              say what selecting them would return:
            </p>
            <ul className="flex max-w-prose flex-col gap-field">
              {unanswered.map((entry) => (
                <li key={`${entry.legend}/${entry.label}`}>
                  {entry.legend} &rarr; {entry.label}: {entry.why}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </aside>
  )
}
