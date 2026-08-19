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
 * ## What is drawn, and what deliberately is not
 *
 * The owner asked to see the actual code here, explained. **Sync does not serve customer source**
 * — `api/app.py` records it as a threat-model ruling: a diff is Sync's own artifact and is served,
 * source is not. That is not a gap this drawer routes around.
 *
 * What the graph *does* hold is a semantic description of the call, recorded by the indexer and
 * governed by `graph-grain.md`'s shapes-not-values rule: the symbol invoked, the argument **keys**
 * sent, the response **fields** read, the nesting depth, and the rung that established the
 * binding. That is what this drawer explains, and for the question a reader actually has — *what
 * does this call do, and what would a vendor change break here* — it is a better answer than the
 * source, because it is exactly the surface a change has to break.
 *
 * The path and line are rendered as an address, so the reader opens the file in their own editor
 * where the source already is.
 */

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

export function CallSiteDetail({ site }: { site: CallSiteRow }) {
  return (
    <div className="flex flex-col gap-section">
      <p className="max-w-prose text-meta text-ink-muted">
        What this call sends, what it reads back, and how the index knows it reaches{" "}
        <span className="font-mono">{site.vendor_id}</span>. The source is not shown — Sync does
        not serve source, so this is the call&rsquo;s recorded shape, which is the surface a vendor
        change actually has to break.
      </p>

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
          The address, for your own editor. Sync does not serve source: a diff it wrote is its own
          artifact and is served, and a customer&rsquo;s file is not.
        </p>
      </div>
    </div>
  )
}
