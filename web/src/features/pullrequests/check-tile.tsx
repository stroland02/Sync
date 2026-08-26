/**
 * One recorded check as a tile: what was checked, the state as a word, the sentence beneath it.
 *
 * It was private to `features/findings/remediation-pane.tsx` while the finding detail was the only
 * screen that drew the chain as tiles. The Pull Request level pins the same two checks under its
 * diff, which is the second use and where `CLAUDE.md` says to factor. It lands beside
 * `verification-chain.ts` because that module already owns `Check` and `checkTone` and the
 * remediation pane already imported both from here — one renderer over one derivation, rather than
 * a second copy that could eventually disagree about how a parked check reads.
 *
 * **The state is a recorded value from a closed vocabulary and is legible without its colour.**
 * `checkTone` gives `waiting`, `not_reached` and `unknown` the neutral tone on purpose: three
 * absences, none of them a verdict, and a run parked on the customer's CI must never wear the tone
 * of one that passed it.
 *
 * The sentence keeps its room rather than being cut to fit the tile — which nothing a state is
 * cannot survive being shortened to the word alone.
 */

import { Tag } from "@/components/tag"
import { checkTone, type Check } from "@/features/pullrequests/verification-chain"

export function CheckTile({ check }: { check: Check }) {
  return (
    <div className="flex min-w-0 flex-col gap-field rounded-control border border-line bg-background p-row">
      <div className="flex min-w-0 flex-wrap items-center gap-field">
        <span className="font-furniture min-w-0 truncate text-ink">{check.label}</span>
        <span className="ml-auto">
          <Tag tone={checkTone(check.state)}>{check.state.replace("_", " ")}</Tag>
        </span>
      </div>
      <p className="text-meta text-ink-muted">{check.detail}</p>
    </div>
  )
}
