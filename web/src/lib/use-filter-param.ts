/**
 * A table filter held in the URL, alongside the offsets it invalidates.
 *
 * Same reasoning as `useOffsetParam`: component state dies on unmount, so browser Back from a
 * finding a reader clicked into loses whatever they had narrowed the table to. A filter in the
 * URL also makes the narrowed view a thing one operator can paste to another, which is most of
 * why a filter is worth having on a table this long.
 *
 * `resets` is the part that is not decoration. A filter changes which rows exist, so the page
 * position measured against the old set means nothing against the new one — narrowing from
 * three hundred rows to two while sitting at offset 250 asks the API for a page past the end
 * and gets an empty one back. That reads on screen as "nothing matches", which is a different
 * and much worse answer than "you are past the end of two rows". Clearing the offsets in the
 * same URL write is what stops the two from ever being observed together.
 */

import { useSearchParams } from "react-router"

/**
 * The value stored under `key`, and a setter that writes it back and clears `resets`.
 *
 * `null` is the unfiltered state and is spelled by the parameter's absence rather than by an
 * empty value, so an unfiltered table's URL is the same URL it had before filtering existed.
 */
export function useFilterParam(
  key: string,
  resets: readonly string[] = [],
): [string | null, (next: string | null) => void] {
  const [searchParams, setSearchParams] = useSearchParams()
  const raw = searchParams.get(key)
  const value = raw === null || raw === "" ? null : raw

  function setValue(next: string | null) {
    setSearchParams((prev) => {
      const updated = new URLSearchParams(prev)
      if (next === null || next === "") {
        updated.delete(key)
      } else {
        updated.set(key, next)
      }
      for (const offsetKey of resets) updated.delete(offsetKey)
      return updated
    })
  }

  return [value, setValue]
}

/**
 * Clear several filters and their offsets in one URL write.
 *
 * Calling two `useFilterParam` setters in a row is the obvious spelling and is wrong: each
 * updater is handed the search params from the current location rather than the result of the
 * call before it, so within one event the second write is computed from a location the first
 * has not reached yet and silently drops it. A control labelled "clear all filters" that
 * clears all but one is a worse affordance than no control, because the table it leaves behind
 * still looks unfiltered.
 */
export function useClearFilters(keys: readonly string[], resets: readonly string[] = []) {
  const [, setSearchParams] = useSearchParams()

  return function clear() {
    setSearchParams((prev) => {
      const updated = new URLSearchParams(prev)
      for (const key of [...keys, ...resets]) updated.delete(key)
      return updated
    })
  }
}
