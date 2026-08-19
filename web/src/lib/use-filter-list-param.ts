/**
 * A multi-select table filter held in the URL, alongside the offsets it invalidates.
 *
 * **M15 Task 4.** `useFilterParam` holds one value, which cannot express what a reader of a
 * forty-integration codebase actually wants: two integrations at once, or the three severities
 * that are not `info`. A single-value filter makes those unreachable rather than tedious — there
 * is no sequence of presses that gets there.
 *
 * The values are repeated parameters (`?vendor=a&vendor=b`) rather than one comma-joined value,
 * because they are vendor and operation identifiers and nothing forbids a comma inside one. A
 * separator that can occur in the data is a parser that is wrong on somebody's repository and
 * wrong silently. `sync.api.app._values_param` reads the same spelling on the other side.
 *
 * **One write, always.** Every mutation here clears `resets` in the same `setSearchParams` call
 * that changes the filter. `CI-W520` is what two writes cost: React Router hands the functional
 * form the *current* params rather than a queued value, so a second write is computed from a
 * location the first has not reached, and one of the two is discarded with no error. It rendered
 * as a pressed option over an unchanged table, which reads as a styling defect for as long as
 * anybody is willing to look at the CSS.
 *
 * Not a history push, unlike `useSelectionParam`: narrowing is a refinement a reader does not
 * expect Back to undo one press at a time. Opening a detail is a place they expect Back to leave.
 */

import { useCallback, useMemo } from "react"
import { useSearchParams } from "react-router"

/**
 * The values chosen under `key`, a toggle for one of them, and a clear for all of them.
 *
 * The unfiltered state is the parameter's **absence** rather than an empty value, so an
 * unfiltered table's URL is the one it had before filtering existed.
 */
export function useFilterListParam(
  key: string,
  resets: readonly string[] = [],
): [readonly string[], (value: string) => void, () => void] {
  const [searchParams, setSearchParams] = useSearchParams()

  // Memoised on the joined form rather than on the array: `getAll` returns a new array on every
  // render, so an unmemoised value would be a fresh reference each time and every query key and
  // effect built from it would see a change that did not happen -- a refetch per render.
  //
  // The separator is U+001F, and it is deliberately a character that cannot appear in a value:
  // these are vendor and operation identifiers, and any printable separator is one that is wrong
  // on somebody's repository and wrong silently. It is invisible in an editor, which is why it
  // is named here -- `_stable_id` in `graph/store.py` joins on the same character for the same
  // reason.
  const raw = searchParams.getAll(key).filter((value) => value !== "")
  const joined = raw.join("")
  const values = useMemo(() => (joined === "" ? [] : joined.split("")), [joined])

  const write = useCallback(
    (next: readonly string[]) => {
      setSearchParams((prev) => {
        const updated = new URLSearchParams(prev)
        updated.delete(key)
        for (const value of next) updated.append(key, value)
        for (const offsetKey of resets) updated.delete(offsetKey)
        return updated
      })
    },
    // `resets` is a literal at every call site, so a join is a stable identity for it without
    // asking each caller to memoise an array it writes inline.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [key, resets.join(","), setSearchParams],
  )

  const toggle = useCallback(
    (value: string) => {
      const current = joined === "" ? [] : joined.split("")
      write(
        current.includes(value)
          ? current.filter((held) => held !== value)
          : [...current, value],
      )
    },
    [joined, write],
  )

  const clear = useCallback(() => write([]), [write])

  return [values, toggle, clear]
}
