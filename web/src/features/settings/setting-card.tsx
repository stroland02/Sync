import type { ReactNode } from "react"

import { InfoHint } from "@/components/info-hint"

export interface SettingCardProps {
  /** The name of this setting */
  title: string
  /**
   * What the setting controls and what constrains it, behind the card's info hint.
   *
   * Owner instruction: remove the settings descriptions. Moved rather than deleted, under the rule
   * `console-surface.md` states -- the distinction is protected, the paragraph explaining it is
   * not. Twelve cards each carried a multi-paragraph block at `text-body`, so the screen read as
   * documentation with controls in the margin. Nothing here was a claim that had to stay visible:
   * `refusalNotice` is the slot for those and it still renders in place.
   *
   * The hint's accessible name does NOT open with "About": the group nav has a button named
   * exactly that, and `getByRole("button", { name: /^About/i })` matched twelve hints as well as
   * the nav item. Three tests caught it.
   */
  description: ReactNode
  /**
   * The interactive control or read-only value rendered on the right side.
   *
   * Optional because a card that only explains something has nothing to put there, and a
   * required-but-empty control reserves a 240px column against no content.
   */
  control?: ReactNode
  /** Optional refusal or invariant notice explaining refused configuration states */
  refusalNotice?: ReactNode
  /** Optional footer with card-scoped actions (Save, Cancel, Status) */
  footer?: ReactNode
}

export function SettingCard({
  title,
  description,
  control,
  refusalNotice,
  footer,
}: SettingCardProps) {
  return (
    <div className="flex flex-col rounded-surface border border-line bg-surface overflow-hidden">
      <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-section p-section">
        <div className="flex flex-col gap-field max-w-xl">
          <div className="flex min-w-0 items-center gap-field">
            <h3 className="min-w-0 text-emphasis font-medium text-ink">{title}</h3>
            <InfoHint label={`${title} — what this controls`}>{description}</InfoHint>
          </div>
          {refusalNotice && <div className="mt-row">{refusalNotice}</div>}
        </div>
        {control !== undefined && (
          <div className="flex flex-col items-start lg:items-end gap-row shrink-0 min-w-[240px]">
            {control}
          </div>
        )}
      </div>
      {footer && (
        <div className="flex items-center justify-between border-t border-line/60 bg-surface-muted/30 px-section py-field text-meta text-ink-muted">
          {footer}
        </div>
      )}
    </div>
  )
}
