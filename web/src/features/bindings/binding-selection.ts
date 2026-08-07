/**
 * Which binding the URL is asking for, and whether this page holds it.
 *
 * The drawer's open state lives in the address bar rather than in component state, for the reason
 * `lib/use-offset-param.ts` already gives about a filter: a reader who clicks out of the drawer and
 * comes back with Back should land where they were, and a binding somebody wants a second opinion
 * on should be a link they can paste. `docs/superpowers/briefs/2026-08-07-substrate-binding-surface.md`
 * ruling 5 records why that is a search parameter through `useFilterParam` rather than a route
 * segment, and why it declares no `resets`.
 *
 * **A call site has no id, so its key is its natural key** — repository, path, line and column, the
 * four fields the table's own row key already joins. `bindingKey` builds it and **nothing ever
 * splits it back apart**. A customer repository may hold a path with a colon in it, and a parser
 * reading the last two segments as line and column would resolve `src/a.ts:42:8/index.ts` to the
 * wrong row; comparing whole strings cannot. `binding-selection.test.ts` holds that case.
 *
 * The third answer is the one this module exists for. A key the current page does not hold is
 * neither the list nor the binding: the row may sit behind a filter, on another page, or outside
 * the repository scope the URL carries. Collapsing it onto `none` tells a reader their link was
 * wrong, and collapsing it onto an empty drawer tells them the call site is gone. Both are claims
 * this console cannot support, so it is its own state and the drawer states it.
 */

import type { BindingCallSite } from "@/api/types"

/** The search parameter the drawer's open state is spelled with. */
export const BINDING_KEY = "binding"

/** The four fields that identify a call site, joined. Compared as a whole, never parsed. */
export function bindingKey(site: BindingCallSite): string {
  return `${site.repo_id}:${site.path}:${site.line}:${site.col}`
}

export type BindingSelection =
  | { kind: "none" }
  | { kind: "resolved"; site: BindingCallSite }
  | { kind: "unresolved"; key: string }

/**
 * What the URL is asking for, against the call sites this page actually has.
 *
 * An empty parameter reads as nothing selected rather than as a key matching nothing: the setter
 * spells the closed state as the parameter's absence, and a hand-edited `?binding=` is the same
 * intention badly spelled.
 */
export function selectBinding(
  key: string | null,
  sites: readonly BindingCallSite[]
): BindingSelection {
  if (key === null || key === "") return { kind: "none" }
  const site = sites.find((candidate) => bindingKey(candidate) === key)
  return site === undefined ? { kind: "unresolved", key } : { kind: "resolved", site }
}
