/**
 * The drawer draws a page and makes claims about a set, and this is where the two are told apart.
 *
 * `changes` is an `ItemPage`: `items` is the window the table behind the drawer is currently
 * showing, and `total` is what the operation actually has. Reading the window and saying something
 * about the set is one sentence away from a lie, and the lie is reachable — `?changes_offset=50` on
 * an operation with one change serves an empty `items` and a `total` of 1, and a drawer that
 * branched on `items.length` would tell the reader the vendor has never changed this operation
 * while the table behind it showed the change.
 *
 * So `everChanged` is a fact about the set and `drawn` is a fact about the page, they are named
 * differently, and `partial` says when the second is short of the first. Nothing here may be
 * derived from `items.length` alone.
 */

import { describe, expect, it } from "vitest"

import type { BindingChange, ItemPage } from "@/api/types"
import { describeChangeSet } from "@/features/bindings/change-set"

function change(id: string): BindingChange {
  return {
    change_id: id,
    kind: "request-parameter-removed",
    severity: "breaking",
    from_version: "2024-04-10",
    to_version: "2024-06-20",
    path_ptr: "/paths/~1v1~1charges/post",
    detected_at: "2026-08-06T19:35:30.509639+00:00",
  }
}

function page(items: BindingChange[], total: number): ItemPage<BindingChange> {
  return { items, total, next_offset: null }
}

describe("describeChangeSet", () => {
  it("says the vendor never changed the operation only when the set is empty", () => {
    expect(describeChangeSet(page([], 0))).toEqual({
      everChanged: false,
      drawn: 0,
      total: 0,
      partial: false,
    })
  })

  it("draws the whole set when one page holds it", () => {
    expect(describeChangeSet(page([change("a")], 1))).toEqual({
      everChanged: true,
      drawn: 1,
      total: 1,
      partial: false,
    })
  })

  it("still says the vendor changed it when the page position is past the only change", () => {
    // `?changes_offset=50` against a set of one. The API answers with no items and a total of 1,
    // and the drawer must not read that as an operation the vendor has never touched.
    expect(describeChangeSet(page([], 1))).toEqual({
      everChanged: true,
      drawn: 0,
      total: 1,
      partial: true,
    })
  })

  it("reports a page shorter than the set as partial, wherever in the set it sits", () => {
    const shown = [change("a"), change("b")]
    expect(describeChangeSet(page(shown, 60))).toEqual({
      everChanged: true,
      drawn: 2,
      total: 60,
      partial: true,
    })
  })
})
