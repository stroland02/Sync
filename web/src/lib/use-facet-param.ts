/**
 * A filter-rail selection held in the URL rather than component state.
 *
 * `use-offset-param`'s reasoning, applied to a facet: component state dies on unmount, so
 * browser Back from a run a reader clicked into would land the table unfiltered while the rail
 * they remember was narrowed. The URL survives navigation — and it also makes a narrowed view
 * shareable, which a triage handoff needs.
 *
 * No vocabulary check here, deliberately. A stale bookmark can carry a value the facet no
 * longer holds, and dropping it would filter the table while showing nothing pressed —
 * `FilterRail` renders an outside-vocabulary selection as its own state instead, so the raw
 * string is what it needs.
 */

import { useSearchParams } from "react-router"

/** The selection stored under `key`, or null for the whole set, and its setter. */
export function useFacetParam(key: string): [string | null, (value: string | null) => void] {
  const [searchParams, setSearchParams] = useSearchParams()
  const selected = searchParams.get(key)

  function setSelected(next: string | null) {
    setSearchParams((prev) => {
      const updated = new URLSearchParams(prev)
      // The whole set is the default, so it stays out of the URL rather than tagging every
      // link with an empty filter.
      if (next === null) {
        updated.delete(key)
      } else {
        updated.set(key, next)
      }
      return updated
    })
  }

  return [selected, setSelected]
}
