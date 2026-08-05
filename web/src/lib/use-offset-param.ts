/**
 * A pagination offset held in the URL rather than component state.
 *
 * Component state dies on unmount, so browser Back from a finding a reader clicked into
 * lands the vendor table at offset zero. The URL survives navigation, which is the one
 * property component state cannot offer here.
 */

import { useSearchParams } from "react-router"

/** An offset stored under `key`, and the setter that writes it back to the URL. */
export function useOffsetParam(key: string): [number, (offset: number) => void] {
  const [searchParams, setSearchParams] = useSearchParams()
  const raw = searchParams.get(key)
  const parsed = raw === null ? NaN : Number(raw)
  const offset = Number.isInteger(parsed) && parsed >= 0 ? parsed : 0

  function setOffset(next: number) {
    setSearchParams((prev) => {
      const updated = new URLSearchParams(prev)
      // Zero is the default, so it stays out of the URL rather than appearing as `?offset=0`
      // on every unpaged vendor link.
      if (next === 0) {
        updated.delete(key)
      } else {
        updated.set(key, String(next))
      }
      return updated
    })
  }

  return [offset, setOffset]
}
