/**
 * The left half of the finding detail: what the graph recorded about this call site.
 *
 * Ordered as the argument runs — the call, then what a vendor changed about it, then the surface
 * the call touches, then how the binding was established. That ordering is stated on screen in one
 * line because this payload carries no event times: nothing here is a chronology, and a reader who
 * assumed one would take the provenance strip for a sequence of events rather than four last-read
 * timestamps.
 *
 * **Six sections, six different nothings.** A missing source window is withheld-by-policy or
 * indexed-before-capture; an empty change list is a counted zero; an empty argument-key set is
 * nothing recorded at this call site. That absence is not zero is the rule `web/CLAUDE.md` names as
 * the one most easily lost in a tidy-up, and it is why each of these is a sentence and not a dash.
 *
 * The reference's lead item on this side is an OpenTelemetry trace with per-span latencies. We hold
 * no runtime trace on this payload and no per-span timing anywhere in the product (B123), so the
 * index-captured source window takes that slot: the same job — *here is what actually runs* —
 * answered by evidence this graph has.
 */

import { Link } from "react-router"

import { NotFoundError } from "@/api/errors"
import type { FindingDetail } from "@/api/types"
import { CodeSnippet, absentSnippetReason } from "@/components/code-snippet"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { type Fact, FactList } from "@/components/fact-list"
import { ProvenanceStrip, RungBadge } from "@/components/provenance"
import { EmptyState, ErrorState, LoadingState, NotFoundState } from "@/components/states"
import { Absent, Formatted } from "@/components/status"
import { ChangeKindTag, SeverityTag } from "@/components/tag"
import { DetailSection } from "@/features/findings/detail-section"
import { orAbsent } from "@/lib/format"

/**
 * A set of recorded strings from the customer's own source, one chip each.
 *
 * A chip here is not a badge claiming a status: an argument key is evidence, so it takes the
 * console's chip anatomy — the weight, the hairline and the control radius `RungBadge` spells — and
 * never one of the four reserved status colours.
 */
function FieldList({ label, values }: { label: string; values: string[] }) {
  return (
    <div className="flex min-w-0 flex-col gap-field">
      <h4 className="furniture text-meta text-ink-muted">{label}</h4>
      {values.length === 0 ? (
        <p className="text-body">
          <Absent>none recorded</Absent>
        </p>
      ) : (
        <ul className="flex flex-wrap gap-row">
          {values.map((value) => (
            <li
              key={value}
              className="rounded-control border border-line bg-background px-field py-field font-mono text-meta"
            >
              {value}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/** The four binding facts the identity row has no room for, label left and value right. */
function bindingFacts(found: FindingDetail): Fact[] {
  return [
    {
      label: "Repository",
      value:
        found.finding.repo_id === null ? (
          <Absent>unknown</Absent>
        ) : (
          <Link
            to={`/repositories/${encodeURIComponent(found.finding.repo_id)}`}
            className="font-mono underline underline-offset-2 break-all"
          >
            {found.finding.repo_id}
          </Link>
        ),
    },
    {
      label: "Symbol",
      value: (
        <span className="font-mono">
          <Formatted value={orAbsent(found.symbol)} />
        </span>
      ),
    },
    {
      label: "SDK version",
      value: (
        <span className="font-mono">
          <Formatted value={orAbsent(found.sdk_version)} />
        </span>
      ),
    },
    { label: "This finding's rung", value: <RungBadge rung={found.finding.binding_source} /> },
  ]
}

export function EvidencePane({
  findingId,
  data,
  isPending,
  error,
  onRetry,
}: {
  findingId: string
  data: FindingDetail | undefined
  isPending: boolean
  /** The read's failure, or `null`. A 404 here is an answer about the finding, not a breakage. */
  error: unknown
  onRetry: () => void
}) {
  if (isPending) return <LoadingState what={`finding ${findingId}`} />

  if (data === undefined) {
    return error instanceof NotFoundError ? (
      <NotFoundState
        headline="That finding is not open."
        detail="The API answered, and the graph holds no open finding with this identifier. It may have been patched, abandoned, or it may never have existed. This is an answer about the finding, not a failure of the console."
        identifier={error.identifier}
      />
    ) : (
      <ErrorState error={error} what={`finding ${findingId}`} onRetry={onRetry} />
    )
  }

  return (
    <>
      <p className="text-meta text-ink-muted">
        Ordered as the argument runs, not as a clock: this payload carries no event times, only when
        each source was last read.
      </p>

      <DetailSection
        heading="The call, in place"
        hintLabel="About the captured window"
        hint="The window the index pass recorded around this call site, numbered from where it sits in the file. It is what the graph captured rather than a live read of the customer's tree, so a window can be older than the file it came from."
      >
        {data.call_site_source !== null ? (
          <CodeSnippet
            className="bg-background"
            code={data.call_site_source.snippet}
            startLine={data.call_site_source.snippet_start_line}
            markLine={data.call_site_source.line}
            label={`Call site, ${data.finding.file ?? "unknown file"}:${data.finding.line ?? "?"}`}
          />
        ) : (
          <p className="max-w-prose text-body">
            <Absent>{absentSnippetReason(data.source_served)}</Absent>
          </p>
        )}
      </DetailSection>

      <DetailSection
        heading="Vendor changes naming this call site"
        hintLabel="About known changes"
        hint="Returned shallow: a change carries an identifier, a kind and a severity here, and no diff text and no publication time. The full record is fetched by identifier from the vendor's own changes."
      >
        {data.known_changes.length === 0 ? (
          <EmptyState
            headline="No vendor change names this call site."
            detail="A counted zero: the read answered and the list came back empty. The finding was raised by something other than a spec diff."
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Change</TableHead>
                <TableHead>Kind</TableHead>
                <TableHead>Severity</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.known_changes.map((change) => (
                <TableRow key={change.change_id}>
                  <TableCell className="font-mono">{change.change_id}</TableCell>
                  <TableCell>
                    <ChangeKindTag kind={change.kind} />
                  </TableCell>
                  <TableCell>
                    <SeverityTag severity={change.severity} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </DetailSection>

      <DetailSection
        heading="What the call site touches"
        hintLabel="About the touched surface"
        hint="The argument keys sent and the response fields read — the surface a vendor change has to break for this finding to matter. Both are recorded by the index pass from the call site's own source."
      >
        <FieldList label="Argument keys" values={data.args_keys} />
        <FieldList label="Response fields read" values={data.response_fields_read} />
      </DetailSection>

      <DetailSection
        heading="The binding, as recorded"
        hintLabel="About this finding's rung"
        hint="The rung is this one finding's own column and always says something definite — it is what a false positive here has to be attributable to. It records how the binding was established, never how much to trust it."
      >
        <FactList facts={bindingFacts(data)} />
      </DetailSection>

      <DetailSection
        heading="Provenance"
        hintLabel="About the two rungs"
        hint="The rung above is this finding's own. The one below describes the whole answer, which is built from every finding naming this call site, and goes null when those disagree."
      >
        <ProvenanceStrip
          provenance={data}
          bindingNullLabel="mixed: more than one detector names this call site and they disagree on the rung — this finding's own rung is under 'The binding, as recorded' above"
        />
      </DetailSection>
    </>
  )
}
