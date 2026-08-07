/**
 * A bar the width of the value it will become.
 *
 * **This replaces nothing in `states.tsx`, and the distinction is the reason it exists.** Those five
 * states answer a question about *a query*: nothing matched, the filter excluded it, the API is not
 * running, this view cannot see it, still loading. Each is a sentence because each is a different
 * fact and a reader has to be able to tell them apart — `.claude/rules/console-surface.md` protects
 * those sentences and `tests/test_console_honesty_sentences.py` fails if one goes missing.
 *
 * A skeleton is the opposite case: **the query is fine and one value has not arrived.** It says
 * nothing on purpose. Putting a sentence there would claim a state the system is not in, and
 * `LoadingState`'s sentence beside eight settled facts would read as though the whole panel were
 * pending.
 *
 * `references/direction/NOTES.md` records where this came from and that it is a gap rather than a
 * preference: "A skeleton, not a spinner. `LAST MIGRATION` renders a grey bar the width its value
 * will be. The console has no skeleton anywhere; every pending state is a sentence."
 *
 * **It does not pulse.** `lib/motion.ts` carries a registry that a Python guard binds to the tree in
 * both directions, and a pulse utility would need a keyframe the design contract permits only for a
 * loading indicator inside `components/ui/`. A bar that is plainly not a value is already legible as
 * one; M4.5-W143 measured that the console runs zero animations at rest on all nine routes and this
 * does not spend that.
 *
 * That sentence originally named the utility, and naming it **put the keyframe in the production
 * bundle.** Tailwind's scanner extracts candidates from raw file text and does not know a comment
 * from code, so a docstring explaining why the console has no animation compiled one in — measured
 * in `dist/assets/*.css` before the wording changed. The Python guards blank comments before
 * scanning, which is right for them and is exactly why none of them could see this; the compiler
 * reads what the compiler reads, so `test_console_design_tokens.py` now scans raw source for the
 * utility prefix as well.
 *
 * `aria-hidden` with a live-region-free `role="presentation"`: the value's own label is already on
 * screen beside it, so announcing "loading" here would be a second thing said about one absence.
 */

import { cn } from "@/lib/utils"

/**
 * `width` is a Tailwind width class, and it is required rather than defaulted.
 *
 * A skeleton whose width is unrelated to its value reflows the layout when the value lands, which is
 * the one thing a skeleton is for. Making the caller state it means the caller has thought about
 * what is coming: `w-16` for a count, `w-40` for a timestamp, `w-full` for a path.
 */
export function Skeleton({ width, className }: { width: string; className?: string }) {
  return (
    <span
      role="presentation"
      aria-hidden="true"
      className={cn("inline-block h-4 rounded-control bg-surface-subtle", width, className)}
    />
  )
}
