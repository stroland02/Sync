/**
 * Which workspace the chassis is attached to, including on screens that do not name one.
 *
 * **Owner report, 2026-08-19: opening Settings detached the codebase.** `/settings` is a
 * destination rather than a level — it configures the deployment, not a repository — so it binds
 * no `repoId`. The chassis read the workspace from the route alone, so on Settings the badge went
 * blank, every repository-scoped row in the rail became unlinkable text, and coming back required
 * choosing the workspace again.
 *
 * The fallback that used to cover this only applied when exactly one repository existed, so it
 * stopped working the moment a second codebase was indexed — the same edge that hid the missing
 * workspace switcher.
 *
 * ## The rule
 *
 * **A route that names a workspace is always right.** The address is the authority, and a
 * remembered value must never override it — that would make a shared link open somebody else's
 * codebase.
 *
 * **A route that names none inherits the last one.** That is what keeps the chassis attached
 * across Settings, and what lets the rail stay navigable there.
 *
 * **A remembered workspace that no longer exists is discarded.** A codebase can be removed
 * between sessions, and a badge naming one the graph no longer holds is a claim nothing supports.
 */

const KEY = "sync.workspace.active"

/** Remember, best-effort. A full quota or private browsing costs the memory, not the navigation. */
export function rememberWorkspace(repoId: string): void {
  try {
    window.localStorage.setItem(KEY, repoId)
  } catch {
    // Nothing to do and nothing worth telling a reader: the session still works, it just does
    // not outlive itself.
  }
}

/** The remembered workspace, or null. */
export function rememberedWorkspace(): string | null {
  try {
    const value = window.localStorage.getItem(KEY)
    return value && value.trim() ? value : null
  } catch {
    return null
  }
}

/**
 * The workspace the chassis should show.
 *
 * Pure, and exported for its test: this is a derivation with a wrong answer — the wrong one being
 * a remembered value winning over an address, which would open a shared link on the wrong
 * codebase.
 */
export function activeWorkspace(
  routeRepoId: string | undefined,
  remembered: string | null,
  known: readonly string[],
): string | null {
  if (routeRepoId !== undefined) return routeRepoId
  if (remembered !== null && known.includes(remembered)) return remembered
  // One codebase is not a choice, so it needs no memory to be the answer.
  return known.length === 1 ? known[0] : null
}
