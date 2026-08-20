/**
 * One call site in full, opened from its row.
 *
 * **Nango's convention, Supabase's form.** Nango's note (§4) is why the row opens a detail at all
 * and why the open row lives in the URL: a reader handing a colleague a link should be handing
 * them the row they are looking at. Supabase's note is why it is a panel beside the list rather
 * than the modal sheet `CI-W514` shipped — their own list-detail is not modal, because a reader
 * working down 165 rows should not have to close one to reach the next.
 *
 * The frame, the title and the close control belong to `DetailLayout`; this is the body.
 *
 * ## What is drawn
 *
 * The window the index pass captured around the call, when the deployment serves source
 * (`SYNC_SERVE_SOURCE`, owner re-ruling 2026-08-19 scoping the threat-model rule in
 * `api/app.py`: bounded captured windows are served; whole files never are). Beneath it, the
 * semantic description the graph holds under `graph-grain.md`'s shapes-not-values rule: the
 * symbol invoked, the argument **keys** sent, the response **fields** read, the nesting depth,
 * and the rung that established the binding — the surface a vendor change actually has to break.
 *
 * The path and line stay rendered as an address for the reader's own editor: the window is a
 * view, never the file.
 */

import { CodeSnippet, absentSnippetReason } from "@/components/code-snippet"
import { InfoHint } from "@/components/info-hint"
import { RungBadge } from "@/components/provenance"
import { Absent } from "@/components/status"
export interface CallSiteRow {
  id: string
  path: string
  line: number
  col: number
  vendor_id: string
  operation_id: string
  symbol: string
  args_keys: string[]
  response_fields_read: string[]
  sdk_version: string | null
  loop_depth: number
  indexed_at: string | null
  snippet?: string | null
  snippet_start_line?: number | null
}

/** A set of recorded strings from the customer's own source, one chip each. */
function KeyList({
  label,
  values,
  absent,
  hint,
}: {
  label: string
  values: string[]
  /** What an empty set means here — never a bare dash. */
  absent: string
  hint: string
}) {
  return (
    <div className="flex flex-col gap-field">
      <div className="flex items-center gap-row">
        <h3 className="furniture text-meta text-ink-muted">{label}</h3>
        <InfoHint label={`About ${label.toLowerCase()}`}>{hint}</InfoHint>
      </div>
      {values.length === 0 ? (
        <p className="text-body">
          <Absent>{absent}</Absent>
        </p>
      ) : (
        <ul className="flex flex-wrap gap-field">
          {values.map((value) => (
            <li
              key={value}
              className="rounded-control border border-line px-field py-field font-mono text-meta"
            >
              {value}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-field">
      <span className="furniture text-meta text-ink-muted">{label}</span>
      <span className="min-w-0 break-words font-mono text-body text-ink">{value}</span>
    </div>
  )
}

export function CallSiteDetail({
  site,
  sourceServed = false,
}: {
  site: CallSiteRow
  /** The page payload's `source_served` — whether this deployment serves captured windows. */
  sourceServed?: boolean
}) {
  return (
    <div className="flex flex-col gap-section">
      <p className="max-w-prose text-meta text-ink-muted">
        What this call sends, what it reads back, and how the index knows it reaches{" "}
        <span className="font-mono">{site.vendor_id}</span>. The recorded shape below is the
        surface a vendor change actually has to break; the window above it is what the index
        pass read at this position.
      </p>

      {/* Owner re-ruling 2026-08-19: bounded index-captured windows are shown where the
          deployment serves them. Absence keeps its two causes apart — policy and pre-capture
          rows are different nothings, and `absentSnippetReason` says which. */}
      {typeof site.snippet === "string" && site.snippet_start_line != null ? (
        <CodeSnippet
          code={site.snippet}
          startLine={site.snippet_start_line}
          markLine={site.line}
          label={`Call site, ${site.path}:${site.line}`}
        />
      ) : (
        <p className="max-w-prose text-meta text-ink-muted">
          <Absent>{absentSnippetReason(sourceServed)}</Absent>
        </p>
      )}

      <div className="grid gap-section sm:grid-cols-2">
        <Fact label="Integration" value={site.vendor_id} />
        <Fact label="Operation" value={site.operation_id} />
        <Fact label="Symbol invoked" value={site.symbol} />
        <Fact
          label="SDK version"
          value={site.sdk_version === null ? <Absent>not recorded</Absent> : site.sdk_version}
        />
        <div className="flex flex-col gap-field">
          <span className="furniture text-meta text-ink-muted">Rung</span>
          <RungBadge rung={"static"} />
        </div>
        <Fact
          label="Nesting"
          value={
            site.loop_depth === 0
              ? "not inside a loop"
              : `inside ${site.loop_depth} loop${site.loop_depth === 1 ? "" : "s"}`
          }
        />
      </div>

      <div className="flex flex-col gap-section border-t border-line pt-section">
        <KeyList
          label="Arguments sent"
          values={site.args_keys}
          absent="no argument keys recorded"
          hint="The argument keys this call passes — keys only, never values. A vendor change that removes or renames one of these breaks this call site, which is why the keys are the surface worth recording. Values are discarded at the observation boundary and never reach a column."
        />
        <KeyList
          label="Response fields read"
          values={site.response_fields_read}
          absent="no response field recorded as read"
          hint="Which fields of the response this code actually reads. A vendor removing a field this call site never touches breaks nothing here — that difference is what lets Sync tell a change that matters from one that does not, and it is why an empty set here is meaningful rather than missing."
        />
      </div>

      <div className="flex flex-col gap-field border-t border-line pt-section">
        <span className="furniture text-meta text-ink-muted">Open it</span>
        <code className="block overflow-x-auto rounded-control border border-line bg-surface-subtle px-field py-field font-mono text-meta text-ink select-all">
          {site.path}:{site.line}:{site.col}
        </code>
        <p className="max-w-prose text-meta text-ink-muted">
          The address, for your own editor. The window above is a bounded capture from the index
          pass, never the live file.
        </p>
      </div>
    </div>
  )
}
