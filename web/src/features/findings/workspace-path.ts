/**
 * The workspace prefix every route carries as of `M14-W386`.
 *
 * `web/src/lib/routes.ts` collapsed two regions into one, so every address is now
 * `/repositories/:repoId/...`. Links built without that prefix still compile — a path is a string
 * — and resolve to nothing, which the console answers with "No screen at this address."
 * **That is how these were found: by opening the screen, not by a type error.**
 *
 * One definition rather than one per file. Two screens needed it and `CLAUDE.md`'s rule is to
 * factor at the second use, not the third, because the third is where the copies have already
 * drifted.
 *
 * `routes.ts` is another lane's file and is not edited here; this reads the shape it declares.
 */
export function workspacePath(repoId: string | undefined): string {
  return `/repositories/${encodeURIComponent(repoId ?? "")}`
}
