import type { ReactNode } from "react"

export interface SettingCardProps {
  /** The name of this setting */
  title: string
  /** Detailed prose explanation of what the setting controls and what constraints apply */
  description: ReactNode
  /** The interactive control or read-only value rendered on the right side */
  control: ReactNode
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
          <h3 className="text-emphasis font-medium text-ink">{title}</h3>
          <div className="text-body text-ink-muted leading-relaxed space-y-2">{description}</div>
          {refusalNotice && <div className="mt-2">{refusalNotice}</div>}
        </div>
        <div className="flex flex-col items-start lg:items-end gap-2 shrink-0 min-w-[240px]">
          {control}
        </div>
      </div>
      {footer && (
        <div className="flex items-center justify-between border-t border-line/60 bg-surface-muted/30 px-section py-field text-meta text-ink-muted">
          {footer}
        </div>
      )}
    </div>
  )
}
