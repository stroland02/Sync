/**
 * The run stream: one row per checkpoint thread, filling a locked viewport and scrolling itself.
 *
 * "One row per run" is the sentence this pane exists to keep honest: a finding retried across
 * generations writes one checkpoint thread per generation, and this does not collapse them the way
 * the single-finding workflow view does. Two generations of one finding are two rows here, not one.
 *
 * **One line per row, and every column truncates.** The reference's log stream reads because its
 * rhythm never breaks; the card this replaced stacked a finding id under a name, expanded an
 * abandon reason inside a cell and hung a liveness chip off an outcome, so one row could be six
 * lines tall. All three moved into the run record pane, where they can be as tall as they are.
 *
 * **No query of its own.** The page owns the one `useRuns` call and hands the page down, so the
 * stream and the status band can never describe different sets.
 */

import {
  Table,
  TableBody,
  TableCell,
  TableEmptyRow,
  TableFrame,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { RelativeTime } from "@/components/relative-time"
import { Absent } from "@/components/status"
import { OutcomeTag } from "@/components/tag"
import type { RunsPage } from "@/api/types"
import { describeOutcome, isRehearsal, recordLine } from "@/features/runs/run-row"

const COLUMNS = 5

export function RunsStream({
  page,
  selected,
  onSelect,
  narrowed,
}: {
  page: RunsPage
  /** The open thread id, or null. */
  selected: string | null
  onSelect: (threadId: string | null) => void
  /** Whether a disposition chip is pressed — which of the two nothings an empty page is. */
  narrowed: boolean
}) {
  return (
    <TableFrame fill className="bg-card">
      <Table className="table-fixed">
        {/* Sticky against the table's own scroll container, on an opaque band: the head is the
            only chrome this pane has, exactly as the reference draws it. */}
        <TableHeader sticky>
          <TableRow>
            <TableHead className="w-[7.5rem]">Checkpoint</TableHead>
            <TableHead className="w-[10rem]">Outcome</TableHead>
            <TableHead className="w-[6rem]">Kind</TableHead>
            <TableHead className="w-[18rem]">Finding</TableHead>
            <TableHead>Record</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {/* Decision 61: the headers stay when there is nothing to list, so the shape of a run is
              legible before there is a run and a reader learns what one IS from a screen with none. */}
          {page.items.length === 0 &&
            (narrowed && page.unfiltered_total > 0 ? (
              <TableEmptyRow colSpan={COLUMNS}>
                <span className="text-ink">No run matches this narrowing.</span> The checkpointer
                holds {page.unfiltered_total.toLocaleString()} runs and none of them carries this
                disposition — clear the chip to see them.
              </TableEmptyRow>
            ) : (
              <TableEmptyRow colSpan={COLUMNS}>
                <span className="text-ink">No run has ever checkpointed.</span> The API answered,
                and the checkpointer holds no thread. That is an answer, not a failure — nothing has
                attempted a repair on this database yet.
              </TableEmptyRow>
            ))}
          {page.items.map((run) => {
            const rehearsal = isRehearsal(run)
            const record = recordLine(run)
            const open = selected === run.thread_id
            return (
              <TableRow
                key={run.thread_id}
                interactive
                aria-selected={open}
                data-state={open ? "selected" : undefined}
                onClick={() => onSelect(run.thread_id)}
                // `primary` is DESIGN.md's declared "the current thing" accent. It carries no
                // glyph and no verdict, which is what lets a colour stand alone here: it says
                // which row is open, not whether the run went well.
                className="data-[state=selected]:border-l-2 data-[state=selected]:border-l-primary"
              >
                <TableCell className="truncate font-mono text-meta text-ink-muted">
                  <RelativeTime iso={run.last_checkpoint_at} />
                </TableCell>
                <TableCell className="truncate">
                  <OutcomeTag outcome={describeOutcome(run.outcome, rehearsal)} />
                </TableCell>
                <TableCell className="truncate font-mono text-meta text-ink-muted">
                  {rehearsal ? "rehearsal" : "live"}
                </TableCell>
                <TableCell className="truncate font-mono text-meta">
                  {/* The id is not stacked under the name: one line per row is the stream's
                      grain, and the id is the first fact in the record pane. */}
                  {run.finding_name === null ? (
                    <Absent>no longer in the graph</Absent>
                  ) : (
                    run.finding_name
                  )}
                </TableCell>
                <TableCell className="truncate font-mono text-meta">
                  {record.absent === undefined ? (
                    record.text
                  ) : (
                    <Absent>{record.absent}</Absent>
                  )}
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </TableFrame>
  )
}
