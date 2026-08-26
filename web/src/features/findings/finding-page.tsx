/**
 * One finding, as a locked viewport split down the middle: the evidence on the left, the proposed
 * remediation on the right, each pane scrolling its own body.
 *
 * **Rebuilt 2026-08-26 against `docs/stitch_sync_developer_console/.../self_healing_incident_inspector/`.**
 * The screen it replaces was a `DetailGrid` — one long scrolling column of metric panels with a
 * 360px fact rail beside it — and the owner's ruling is the evidence/remediation split. `DetailGrid`
 * survives for its two other callers; nothing here uses it.
 *
 * **The right pane is deliberately not gated on `useFinding`.** The checkpointer is a different
 * database from the graph and outlives the re-derived `finding` row, so the run, the patch and the
 * dismissal all still answer on a page whose left pane 404s — which is exactly the finding whose
 * run is most worth reading.
 *
 * **Four of the seven facts a detail would want are not in this payload, and none is invented.**
 * `sync.api.app.finding_detail` reads a risk row and forwards two of its fields, so this level holds
 * no first-detection time — `indexed_at` is when the index last read the call site, which is why the
 * identity band labels it *Indexed* and says so behind the ⓘ. B122 carries the payload change and
 * why each substitute was refused.
 *
 * **The status band states that nothing here pages, and counts the one countable set.** A detail has
 * one subject, so there is no record window to describe. The figure beside it is `known_changes`,
 * and it is null only when the read has not answered: a finding no vendor change names is a counted
 * zero and says `0`.
 *
 * What the reference asks for and this refuses is recorded on the pane that would have carried it —
 * `remediation-pane.tsx` for the confidence bar, the spinning chip and the three write actions,
 * `evidence-pane.tsx` for the trace waterfall. The one refusal that belongs to this file is the
 * slide-over sheet: this is a spec-pinned routed level with its own address, and a modal cannot be
 * linked, reloaded or opened from the command palette.
 */

import type { ReactNode } from "react"
import { Link, useParams } from "react-router"
import { ScanSearch, Wrench } from "lucide-react"

import { NotFoundError } from "@/api/errors"
import { useFinding, useWorkflow } from "@/api/queries"
import type { FindingDetail } from "@/api/types"
import { InfoHint } from "@/components/info-hint"
import { KpiStrip } from "@/components/kpi-strip"
import { PanelPane } from "@/components/pane"
import { Absent } from "@/components/status"
import { SeverityTag } from "@/components/tag"
import { EvidencePane } from "@/features/findings/evidence-pane"
import { Pending } from "@/features/findings/pending"
import { describeRemediation } from "@/features/findings/remediation"
import { RemediationBadge, RemediationPane } from "@/features/findings/remediation-pane"
import { TicketAction } from "@/features/tickets/ticket-action"
import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"
import { UnknownRoute } from "@/layouts/unknown-route"
import { findingTitle } from "@/lib/detail-title"
import { formatTimestamp } from "@/lib/format"
import { vendorHref } from "@/lib/hrefs"

const QUESTION = "What this call site calls, and how the system knows it does."

/**
 * The subject line: the one row that is true in every state.
 *
 * The identifier comes from the URL, so it is on screen before any request is made and stays there
 * when one fails. The four fields beside it come from the payload, so when there is no payload the
 * band says which nothing it is **once** rather than four times: the same sentence repeated across
 * a row is the "too much information" failure the brief names, and the sentence is about the read
 * rather than about any one field.
 *
 * A band rather than a caption under the title. `ScreenFrame`'s `subtitle` renders inside a
 * `max-w-prose` paragraph, which is right for a sentence and wrong for a row of chips, mono values
 * and a link; the frame's own `identity` slot was specified for this and did not land with the
 * chassis slice, and that file belongs to the frame's task rather than this screen's.
 */
function IdentityBand({
  repoId,
  findingId,
  data,
  failure,
}: {
  repoId: string | undefined
  findingId: string
  data: FindingDetail | undefined
  failure: ReactNode | null
}) {
  const identifier = (
    <code className="font-mono text-meta break-all text-ink-muted select-all">{findingId}</code>
  )

  if (data === undefined) {
    return (
      <Band>
        {identifier}
        {failure ?? <Pending />}
      </Band>
    )
  }

  return (
    <Band>
      {data.finding.severity === null ? (
        <Absent>no severity recorded</Absent>
      ) : (
        <SeverityTag severity={data.finding.severity} />
      )}
      {identifier}
      <Link
        to={vendorHref(repoId ?? "", data.vendor)}
        className="font-mono underline underline-offset-2"
      >
        {data.vendor}
      </Link>
      <code className="font-mono break-all">
        {data.finding.file}:{data.finding.line}
      </code>
      <span className="flex items-center gap-field text-ink-muted">
        Indexed{" "}
        {data.indexed_at === null ? (
          <Absent>not recorded</Absent>
        ) : (
          <time dateTime={data.indexed_at}>{formatTimestamp(data.indexed_at)}</time>
        )}
        <InfoHint label="About the indexed time">
          When the index pass last read this call site. It is not when the finding was detected —
          this payload carries no detection time, and reading it as the finding's age would date the
          finding to whenever the index last ran.
        </InfoHint>
      </span>
    </Band>
  )
}

function Band({ children }: { children: ReactNode }) {
  return (
    <div
      data-testid="finding-identity"
      className="flex shrink-0 flex-wrap items-center gap-section rounded-surface border border-line bg-card px-section py-row text-meta"
    >
      {children}
    </div>
  )
}

export function FindingPage() {
  // A URL is user input, so the identifier is checked here rather than assumed. The query lives one
  // level down so that check happens before a request is made for it.
  const { repoId, findingId } = useParams<{ repoId: string; findingId: string }>()
  if (findingId === undefined) return <UnknownRoute />
  return <FindingDetailPage repoId={repoId} findingId={findingId} />
}

function FindingDetailPage({
  repoId,
  findingId,
}: {
  repoId: string | undefined
  findingId: string
}) {
  const query = useFinding(findingId)
  const run = useWorkflow(findingId)
  const remediation = describeRemediation({
    data: run.data,
    missing: run.isError && run.error instanceof NotFoundError,
    failed: run.isError,
  })

  // Short, because the left pane's own state panel carries the same answer in full: five rows
  // spelling out that panel's sentence would be one fact written six times.
  const failure = query.isError ? (
    query.error instanceof NotFoundError ? (
      <Absent>this finding is not open</Absent>
    ) : (
      <Absent>the API did not answer</Absent>
    )
  ) : null

  const title =
    query.data === undefined ? null : findingTitle(query.data.vendor, query.data.operation)

  // Gated on `query` alone because `query` alone is what it reads: the shallow list is on the
  // finding payload, so the run being in flight cannot make this number wrong.
  const knownChanges = query.isSuccess ? query.data.known_changes.length : null
  // Which absence, in words. Null here means nothing answered, never a count that came back zero,
  // so the scope may not assert the measurement happened until it has.
  const knownChangesScope = query.isSuccess
    ? "vendor changes naming this call site, shallow"
    : query.isError
      ? query.error instanceof NotFoundError
        ? "this finding is not open"
        : "the API did not answer"
      : "still asking"

  const status: StatusSegment[] = [
    { kind: "none", why: "one subject — nothing here pages" },
    {
      kind: "figure",
      label: "Known changes",
      value: knownChanges === null ? null : knownChanges.toLocaleString(),
      scope: knownChangesScope,
    },
  ]

  return (
    <ScreenFrame
      layout="locked"
      status={status}
      title={title?.name ?? undefined}
      subtitle={title?.absent ?? QUESTION}
    >
      {/* Portals into the chassis stats bar, so it draws nothing in place and costs the locked
          column no height. `Known changes` is deliberately not a tile: it is already the status
          band's figure, and a tile restating its own footer at tile weight is what
          `kpi-strip.tsx` forbids. */}
      <KpiStrip
        items={[
          {
            label: "Argument keys",
            value: countTile(query, (found) => found.args_keys.length),
            note: "recorded at this call site by the index pass",
          },
          {
            label: "Response fields read",
            value: countTile(query, (found) => found.response_fields_read.length),
            note: "recorded at this call site by the index pass",
          },
          {
            label: "Runs on this finding",
            value: run.isPending ? (
              <Pending />
            ) : run.data !== undefined ? (
              run.data.generation_count.toLocaleString()
            ) : run.error instanceof NotFoundError ? (
              <Absent>no run recorded</Absent>
            ) : (
              <Absent>not answered</Absent>
            ),
            note: "generations the checkpointer holds — this page reads the newest",
          },
        ]}
      />

      {/* One column rather than two children of the content band, which puts `section` between the
          subject line and the panes it names instead of the band's 32px. Measured at 1366×768: the
          split has 321px to spend and the 16px is a fifth of a section heading. */}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-section">
        <IdentityBand repoId={repoId} findingId={findingId} data={query.data} failure={failure} />

        {/* `min-h-0` on the row and on each pane is what makes the panes scroll instead of the page
            growing; below `xl` it stacks into two half-height panes, which still scroll their own
            bodies rather than handing the scroll back to a locked chassis. */}
        <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-section xl:flex-row">
          <PanelPane
            label="Evidence"
            icon={ScanSearch}
            bodyClassName="flex min-w-0 flex-col gap-section p-section"
          >
            <EvidencePane
              findingId={findingId}
              data={query.data}
              isPending={query.isPending}
              error={query.isError ? query.error : null}
              onRetry={() => void query.refetch()}
            />
          </PanelPane>

          <PanelPane
            label="Remediation"
            icon={Wrench}
            actions={<RemediationBadge remediation={remediation} />}
            bodyClassName="flex min-w-0 flex-col gap-section p-section"
            footerClassName="h-auto items-stretch px-section py-row text-body"
            footer={
              repoId === undefined ? (
                <span className="text-ink-muted">
                  This address carries no workspace, so the ticket control cannot be offered here.
                </span>
              ) : (
                <TicketAction repoId={repoId} findingId={findingId} />
              )
            }
          >
            <RemediationPane
              repoId={repoId}
              findingId={findingId}
              nodes={run.data?.nodes}
              remediation={remediation}
            />
          </PanelPane>
        </div>
      </div>
    </ScreenFrame>
  )
}

/** A counted set from the finding payload, or which nothing stands in its place. */
function countTile(
  query: ReturnType<typeof useFinding>,
  count: (found: FindingDetail) => number,
): ReactNode {
  if (query.data !== undefined) return count(query.data).toLocaleString()
  if (query.isError) {
    return query.error instanceof NotFoundError ? (
      <Absent>not open</Absent>
    ) : (
      <Absent>not answered</Absent>
    )
  }
  return <Pending />
}
