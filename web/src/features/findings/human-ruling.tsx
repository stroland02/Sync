/**
 * Where a human ruling on a finding stands, as prose rather than a control.
 *
 * Read-only, on the owner's ruling of 2026-08-19: the route accepts a POST and no screen sends
 * one. What it owes is the standing, because without it a finding somebody deliberately set aside
 * and a finding nobody has opened render as the same screen.
 *
 * It was private to `remediation-pane.tsx` while the finding detail was the only screen that asked.
 * The Pull Request level asks the same question of the same finding — a pull request open against a
 * finding a human has already dismissed is a materially different thing to review — so this is the
 * second use and the renderer is one renderer.
 *
 * **`history_count` is rendered whenever it is not one, in both branches.** The store's own
 * docstring is explicit that `dismissed: false` covers "never touched" and "dismissed, then
 * restored" alike, and those are different facts about how settled a judgement is. A count on the
 * dismissed branch and none on the restored branch would hide the flip in exactly the direction
 * that flatters the system.
 *
 * `<Absent>` on failure rather than silence: a row that disappears when a request fails reads as
 * "nobody has dismissed this", which is a claim no screen would have earned.
 */

import type { DismissalState } from "@/api/types"
import { Absent } from "@/components/status"
import { Pending } from "@/features/findings/pending"

/** The four states a reader of this fact can be in, and they are four different claims. */
export type RulingState = DismissalState | null | "pending" | "failed"

/**
 * The standing as a single word from a closed vocabulary, for a cell that has room for one.
 *
 * `null` means nothing has answered — never a ruling that came back empty — so a caller renders
 * which nothing it is rather than a word. Deliberately not a third word for "restored": the
 * standing of a finding dismissed and then restored *is* open, and the changes of mind are the
 * history the full rendering carries beneath it.
 */
export function rulingWord(state: RulingState): "open" | "dismissed" | null {
  if (state === "pending" || state === "failed") return null
  if (state === null) return "open"
  return state.dismissed ? "dismissed" : "open"
}

export function HumanRuling({ state }: { state: RulingState }) {
  if (state === "pending") return <Pending />
  if (state === "failed") return <Absent>the API did not answer</Absent>
  if (state === null || !state.dismissed) {
    return (
      <div className="flex flex-col gap-field text-body">
        <span>Open — nobody has dismissed this</span>
        {state !== null && state.history_count > 0 && (
          <span className="text-meta text-ink-muted">
            Dismissed and restored{" "}
            {state.history_count === 1 ? "once" : `${state.history_count} times`} before now. The
            current standing is open; the changes of mind are the history behind it.
          </span>
        )}
      </div>
    )
  }
  return (
    <div className="flex flex-col gap-field text-body">
      <span>
        Dismissed as <span className="font-mono">{state.reason}</span>
      </span>
      <span className="text-meta text-ink-muted">
        Recorded by <span className="font-mono">{state.actor ?? "an actor the row did not name"}</span>
        {state.history_count > 1 && (
          <> — one of {state.history_count} rulings on this finding, and the one standing now.</>
        )}
        {state.history_count <= 1 && (
          <>. Dismissing is a command-line action; this console reads it.</>
        )}
      </span>
    </div>
  )
}
