/**
 * The screen's status band: what is on screen, counted, and over what scope.
 *
 * **A row of typed segments rather than one count, because four screens make one count false.**
 * `RunsPage` counts runs at workspace scope beside corpus attempts at deployment scope;
 * `MetricsPage` has five independent fetches and no instant at which it is loaded; `SolutionsPage`
 * holds three scopes in one content region; `DetectorsPage` has four countable regions. A single
 * number under any of them would be true of one region and a lie about the rest.
 */

import type { ReactNode } from "react"

import { PageControls } from "@/components/page-controls"
import { Absent } from "@/components/status"

/**
 * The closed vocabulary a screen may say about itself.
 *
 * `none` is not the absence of a segment — it is a screen stating that nothing here pages, with
 * the reason. A blank strip would render "this screen has no records" and "this screen has not
 * answered yet" as the same nothing, which is the distinction the console exists to keep.
 */
export type StatusSegment =
  | { kind: "records"; label: string; text: string | null; paging?: PagingSegment }
  | { kind: "listing"; label: string; text: string }
  | { kind: "figure"; label: string; value: string | null; scope?: string }
  | { kind: "note"; text: string }
  | { kind: "none"; why: string }

export interface PagingSegment {
  offset: number
  limit: number
  shown: number
  total: number
  /** The scope's count with no filter applied. Decision 60: with a filter active the count says
      what it excluded, because a bare range under a narrowed table reads as the whole set. */
  unfilteredTotal?: number
  nextOffset: number | null
  busy: boolean
  onOffsetChange: (offset: number) => void
}

function SegmentBody({ segment }: { segment: StatusSegment }) {
  switch (segment.kind) {
    case "records":
    case "listing":
      return (
        <>
          <span className="text-ink-muted">{segment.label}</span>{" "}
          {segment.kind === "listing" ? segment.text : (segment.text ?? <Absent />)}
        </>
      )
    case "figure":
      return (
        <>
          <span className="text-ink-muted">{segment.label}</span>{" "}
          <span className="font-mono">{segment.value ?? <Absent />}</span>
          {segment.scope ? <span className="text-ink-muted"> · {segment.scope}</span> : null}
        </>
      )
    case "note":
      return <span className="text-ink-muted">{segment.text}</span>
    case "none":
      return <span className="text-ink-muted">{segment.why}</span>
  }
}

/**
 * `segments` is required and may not be empty — a screen that publishes nothing publishes
 * `{ kind: "none" }` and says why.
 */
export function StatusBand({ segments, trailing }: { segments: StatusSegment[]; trailing?: ReactNode }) {
  const paged = segments.find(
    (s): s is Extract<StatusSegment, { kind: "records" }> => s.kind === "records" && !!s.paging
  )

  return (
    <div
      data-band="status"
      className="flex flex-wrap items-center gap-x-section gap-y-field border-t border-line px-frame py-field text-meta"
    >
      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-section gap-y-field">
        {segments.map((segment, index) => (
          <span key={index} data-status-segment={segment.kind} className="min-w-0">
            <SegmentBody segment={segment} />
          </span>
        ))}
      </div>
      {paged?.paging ? (
        <div className="shrink-0">
          <PageControls {...paged.paging} />
        </div>
      ) : null}
      {trailing}
    </div>
  )
}
