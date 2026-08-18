import type { ReactNode } from "react"

/**
 * A value that has not arrived yet, rendered as the word rather than as a shape.
 *
 * **Owner decision 36.** A skeleton is a grey block the width of a number, and a reader completes
 * the shape — they see a populated layout whose figures are merely late. A console that refuses to
 * let absence look like zero cannot let pending look like a value, and the two refusals are the
 * same argument.
 *
 * It also rules out the other way of faking continuity: stale data held on screen and dimmed, which
 * shows a figure no longer known to be true.
 *
 * **Four states, and none may collapse into another** — `never-measured`, `measured zero`,
 * `cannot-tell`, and this one, `not-yet-arrived`. They are four different sentences about the same
 * empty space, and a screen rendering any two the same way is the defect the decision names. In
 * this lane they are `<Absent>` with its own wording, a real value of `0` beside its denominator,
 * `<Absent>the API did not answer</Absent>`, and `<Pending>`.
 *
 * Lives here rather than beside `Absent` in `components/status.tsx`, which is where it belongs,
 * because five lanes are editing `web/` and a shared file is where they collide. It is one import
 * away from being hoisted, and `CI-W410` says so in its report.
 */
export function Pending({ children }: { children?: ReactNode }) {
  return (
    <span className="text-ink-muted" data-state="pending">
      {children ?? "loading"}
    </span>
  )
}
