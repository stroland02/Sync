/**
 * What the drawer may say about an operation's vendor changes, and what it may only say about the
 * page it is drawing from.
 *
 * `changes` is an `ItemPage`. `items` is the window the table behind the drawer currently holds
 * and `total` is what the operation has, and the two disagree the moment a reader pages. Every
 * sentence the drawer renders about vendor changes reads one of the fields below rather than
 * `items.length`, because the shipped first version of that edge branched on the page and would
 * have told a reader at `?changes_offset=50` that the vendor has never changed an operation whose
 * change was on the page they had just left.
 *
 * `partial` is deliberately position-free. A page short of its set says nothing about *where* the
 * rest are — after one Next they are behind the reader, not ahead — so it answers whether the
 * drawing is complete and never which direction the remainder lies in.
 */

import type { BindingChange, ItemPage } from "@/api/types"

export interface ChangeSet {
  /** Whether the vendor has ever changed this operation. A fact about the set. */
  everChanged: boolean
  /** How many changes the drawer draws: what the page behind it holds. A fact about the page. */
  drawn: number
  /** How many the operation has. */
  total: number
  /** Whether the page is short of the set, so the drawing is part of the answer. */
  partial: boolean
}

export function describeChangeSet(changes: ItemPage<BindingChange>): ChangeSet {
  return {
    everChanged: changes.total > 0,
    drawn: changes.items.length,
    total: changes.total,
    partial: changes.total > changes.items.length,
  }
}
