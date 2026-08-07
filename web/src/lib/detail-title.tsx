/**
 * What each of the three detail levels puts at the display step.
 *
 * `PageHeader`'s `h1` is the one element on a route permitted `text-display`, so whatever it holds
 * is the page's only focal point. Until M7-W193 all three detail routes spent it on the 32-character
 * finding identifier — measured on `/findings/9f176dea…` at 348x156px inside the 360px rail, wrapped
 * to four lines, a 253px header against Fleet's 104px. An identifier is not a name: nobody reads it,
 * nobody remembers it, and it tells a reader nothing about the subject they navigated to.
 *
 * So a title here is assembled from the parts the payload carried, and it obeys one rule the tests
 * hold: **a part the payload did not carry is stated, never dropped and never filled.** Every
 * function returns both halves — the name it could build, and the absence it has to say — because a
 * name silently one part short reads as a complete name for a different thing.
 *
 * The identifier has not left the screen. It is a monospace fact in each rail, in full and
 * selectable, which is the register a value you copy rather than read belongs in.
 *
 * **This module states no absence it did not derive itself.** The pull request's two phrases come
 * from `features/pullrequests/bundle-facts.ts`, which keys them on the run's outcome, and are passed
 * in rather than restated: `lib/` importing a feature would be backwards, and a second vocabulary
 * for the same four nothings is the defect that file was written to stop.
 *
 * The one component here sits beside the derivation rather than in `components/` because a title
 * that renders its own absence is one decision, and splitting it across two files named the same
 * thing is how the two halves start disagreeing about which nothing they are showing.
 */

import { Absent } from "@/components/status"

/** A name, and whichever part of it the payload could not supply. Never both null. */
export interface DetailTitle {
  /** The parts that were carried, joined for display, or `null` when none were. */
  name: string | null
  /** What is missing from the name, in words, or `null` when nothing is. */
  absent: string | null
}

/** Between two parts of one name. Not a separator any part may itself contain. */
const JOIN = " · "

export const NO_VENDOR = "the payload names no vendor for this call site"
export const NO_OPERATION = "this binding names no operation"
export const NO_GENERATION = "the checkpointer did not count this finding's runs"

/** A value the payload carried, or `null` for the empty string it sends instead of one. */
function carried(value: string | null): string | null {
  return value === null || value === "" ? null : value
}

function assemble(parts: (string | null)[], absent: string | null): DetailTitle {
  const carriedParts = parts.filter((part): part is string => part !== null)
  return { name: carriedParts.length === 0 ? null : carriedParts.join(JOIN), absent }
}

/**
 * The Finding level: which vendor, and which operation on it.
 *
 * Severity and repository would both belong here and neither is on this payload — B122 — so the
 * name is built from what `FindingDetail` actually holds. `vendor` is typed non-null and is still
 * checked, because it arrives from the transport rather than from this codebase.
 */
export function findingTitle(vendor: string, operation: string | null): DetailTitle {
  const namedVendor = carried(vendor)
  const namedOperation = carried(operation)
  if (namedVendor === null) return assemble([namedOperation], NO_VENDOR)
  return assemble([namedVendor, namedOperation], namedOperation === null ? NO_OPERATION : null)
}

/**
 * The Solution Workflow level: which run this is, among the runs on this finding.
 *
 * `generation_count` is how many threads the checkpointer holds for the finding and this route
 * always answers with the newest, so the newest is the `generation_count`-th run. That ordinal is
 * not the thread's generation suffix, which `sync.cli` numbers from zero — the rail carries
 * `thread_id` in full for a reader who needs the suffix itself.
 *
 * **The finding's own name is deliberately not here.** It is not on this payload: the checkpointer
 * is a different database from the graph, and fetching the finding to title this page would put the
 * page's only focal point behind a query that 404s for every patched or abandoned finding — which is
 * exactly the run most worth reading.
 */
export function runTitle(generationCount: number): DetailTitle {
  if (generationCount < 1) return { name: null, absent: NO_GENERATION }
  return { name: `Run ${generationCount}`, absent: null }
}

/**
 * The Pull Request level: which pull request, pushed from which branch.
 *
 * Both parts are lifted out of untyped node evidence, so either can be absent on a real run — and
 * the branch can exist where the number does not, on a run that pushed and then abandoned. The
 * branch names the attempt in that case, which is a truer subject for this page than a sentence
 * about the pull request that never happened; the sentence is the `absent` half.
 */
export function pullRequestTitle(
  prNumber: string | null,
  branch: string | null,
  absentPullRequest: string,
  absentBranch: string,
): DetailTitle {
  const number = carried(prNumber)
  const named = carried(branch)
  if (number === null) return assemble([named], absentPullRequest)
  const hashed = number.startsWith("#") ? number : `#${number}`
  return assemble([hashed, named], named === null ? absentBranch : null)
}

/**
 * A derived title inside `PageHeader`'s `h1`, with its absence under it in the body register.
 *
 * The absence phrase drops out of the display step deliberately. It is a sentence, and a sentence at
 * 46px with `--text-display`'s tracking is neither readable nor the page's subject — but it must
 * still be on screen, so it takes its own line at the register every other qualification on the
 * console wears. `font-normal` and `tracking-normal` are resets: `--text-body` declares neither, so
 * without them the phrase inherits the display step's weight and its −0.045em.
 */
export function DetailTitleText({ title }: { title: DetailTitle }) {
  return (
    <>
      {title.name}
      {title.absent !== null && (
        <span className="block text-body font-normal tracking-normal">
          <Absent>{title.absent}</Absent>
        </span>
      )}
    </>
  )
}
