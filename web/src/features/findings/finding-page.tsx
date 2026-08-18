/**
 * One finding: the binding in full, and the vendor changes that name it.
 *
 * Two rungs on one screen, and they answer different questions. `finding.binding_source` is
 * this finding's own column and always says something definite — it is what a false positive
 * here has to be attributable to. The envelope's rung describes the whole answer, which is
 * built from every finding naming this call site, and goes null when those disagree. Showing
 * only the envelope's would lose the definite value at the exact moment it matters. That
 * distinction used to live only here; the provenance panel's caption now says it on screen,
 * which is where a reader needs it.
 *
 * ## Ported onto the vendored substrate by M7-W178
 *
 * `docs/superpowers/briefs/2026-08-07-substrate-finding.md` is the mapping table this port was
 * gated on. Read that before porting a level, not this docstring.
 *
 * **This is the first detail-shaped level, and the fact rail is a left column rather than a band.**
 * Vendor, API Services and the Binding surface spell `lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]`
 * — content left, facts right, tables full width beneath — because each of them is a list and a
 * table wants the frame. A detail has one subject, so the grid inverts: a 360px rail carrying the
 * facts and the links down, and the content column beside it. Below `lg` it stacks, because a
 * definition list reads the same at either width.
 *
 * **The header spans both columns, as of M7-W193.** It was inside the 360px rail, which is what made
 * the title wrap; it is now the grid's first row across rail and content, so the name has the page's
 * width. `lib/detail-title.tsx` carries what the title is now made of and why it is no longer the
 * identifier.
 *
 * **Four of the seven facts a rail would want are not in this payload, and none is invented.**
 * `sync.api.app.finding_detail` reads a risk row and forwards two of its fields, so this level
 * holds no severity of its own, no repository, and no call-site path or line — the severity on
 * screen belongs to a vendor change and says something different, and `indexed_at` is when the
 * index last read the call site rather than a first detection. B122 carries the payload change and
 * the brief's ruling 3 carries why each substitute was refused.
 *
 * **This level asks the checkpointer for the first time.** `useWorkflow` answers the Remediation
 * fact and gates the pull-request link, which would otherwise be a claim the console cannot support.
 * Two consequences: the page polls while a run is in flight, exactly as the Solution Workflow level
 * does, and the level below this one now opens against a warm cache because both read one query key.
 */

import type { ReactNode } from "react"
import { Link, useParams } from "react-router"

import { NotFoundError } from "@/api/errors"
import { useFinding, useWorkflow } from "@/api/queries"
import type { FindingDetail } from "@/api/types"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { type Fact, FactList } from "@/components/fact-list"
import { MetricPanel } from "@/components/metric-panel"
import { ProvenanceStrip, RungBadge } from "@/components/provenance"
import { Pending } from "@/features/findings/pending"
import { EmptyState, ErrorState, LoadingState, NotFoundState } from "@/components/states"
import { Absent, Formatted } from "@/components/status"
import {
  describeRemediation,
  reachedPullRequest,
  type RemediationStanding,
  type RemediationState,
} from "@/features/findings/remediation"
import { workspacePath } from "@/features/findings/workspace-path"
import { DetailTitleText, findingTitle } from "@/lib/detail-title"
import { formatFindingBadge, orAbsent } from "@/lib/format"
import { Button } from "@/components/ui/button"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { DetailGrid } from "@/layouts/detail-grid"
import { PageHeader } from "@/layouts/page-header"
import { UnknownRoute } from "@/layouts/unknown-route"

const DEFAULT_QUESTION = "What is this finding, and what binding does it rest on?"

/**
 * A set of recorded strings from the customer's own source, one chip each.
 *
 * A chip here is not a badge claiming a status: an argument key is evidence, so it takes the
 * console's chip anatomy — the weight, the hairline and the control radius `RungBadge` spells — and
 * never one of the four reserved status colours.
 */
function FieldList({ label, values }: { label: string; values: string[] }) {
  return (
    <div className="flex flex-col gap-field">
      <h3 className="furniture text-meta text-ink-muted">{label}</h3>
      {values.length === 0 ? (
        <p className="text-body">
          <Absent>none recorded</Absent>
        </p>
      ) : (
        <ul className="flex flex-wrap gap-row">
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

/**
 * How the newest run stands, as the rail's one remediation row.
 *
 * Four kinds of nothing before there is anything to say, and they are not interchangeable: the
 * query is still in flight, the checkpointer holds no run for this finding, the request did not
 * produce an answer, or a run exists. `remediation.ts` is where they are told apart and why.
 *
 * The sentence under a retried finding points at the fleet's runs table rather than at a link this
 * route cannot serve: `GET /api/workflows/{finding_id}` answers with the newest generation only, and
 * `sync.dashboard.fleet.runs` is the query that lists every generation as its own row.
 */
function remediationFact(state: RemediationState): ReactNode {
  if (state.kind === "pending") return <Pending />
  if (state.kind === "none") {
    return <Absent>the checkpointer holds no run for this finding</Absent>
  }
  if (state.kind === "unavailable") return <Absent>the API did not answer</Absent>

  return (
    <div className="flex flex-col gap-field">
      <span>{standingWord(state.standing, state.outcome)}</span>
      {state.retried && (
        <span className="text-meta text-ink-muted">
          The newest of {state.generations} runs on this finding. The others are rows on the fleet's
          runs table; this level can see only that they exist.
        </span>
      )}
    </div>
  )
}

function standingWord(standing: RemediationStanding, outcome: string | null): ReactNode {
  if (standing === "in-flight") return "In flight — no outcome written yet"
  if (standing === "opened") return "Opened a pull request"
  if (standing === "abandoned") return "Abandoned"
  if (standing === "reported") return "Reported, not patched"
  // Named rather than folded into whichever branch fell through last, which is the rule
  // `features/workflows/run-outcome.tsx` states at its own final branch: an unknown outcome
  // rendered as a known one is a confident wrong verdict.
  return (
    <>
      <span className="font-mono">{String(outcome)}</span> — an outcome this console has not caught
      up with
    </>
  )
}

/**
 * The finding's own facts, label left and value right, in the rail beside the content.
 *
 * Three states per fact and they are three different claims, the same three every ported level
 * spells: `<Pending>` writes the word where the value goes while the query is in flight,
 * `<Absent>` says it failed, and a value is a
 * value. Remediation is answered by a second query and carries its own four.
 *
 * `failure` is the caller's sentence rather than a boolean, because this level can fail two ways
 * and only one of them is silence. A 404 here is the API answering that the graph holds no open
 * finding, and rendering "the API did not answer" over that would be a false report of the failure
 * the reader is looking at.
 *
 * The identifier is the first row and wears neither of those three states: it comes from the URL, so
 * it is on screen before any request is made and stays there when one fails. It is a `<code>` at the
 * meta step rather than the page's title, because a 32-character hex string is a value a reader
 * copies rather than reads — `lib/detail-title.tsx` carries what it cost to have it at 46px instead.
 */
function findingFacts(
  repoId: string | undefined,
  findingId: string,
  data: FindingDetail | null,
  failure: ReactNode | null,
  remediation: RemediationState,
): Fact[] {
  function fact(render: (found: FindingDetail) => ReactNode): ReactNode {
    if (data !== null) return render(data)
    if (failure !== null) return failure
    return <Pending />
  }

  return [
    {
      label: "Identifier",
      value: (
        <code className="font-mono text-meta break-all select-all">{findingId}</code>
      ),
    },
    {
      label: "Severity",
      value: fact((found) => (
        <span className="font-mono">
          <Formatted value={orAbsent(found.finding.severity)} />
        </span>
      )),
    },
    {
      label: "Repository",
      value: fact((found) =>
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
      ),
    },
    {
      label: "Call site",
      value: fact((found) => (
        <code className="font-mono text-meta break-all">
          {found.finding.file}:{found.finding.line}
        </code>
      )),
    },
    {
      label: "Vendor",
      value: fact((found) => (
        <Link
          to={`${workspacePath(repoId)}/vendors/${encodeURIComponent(found.vendor)}`}
          className="font-mono underline underline-offset-2"
        >
          {found.vendor}
        </Link>
      )),
    },
    {
      label: "Operation",
      value: fact((found) => (
        <span className="font-mono">
          <Formatted value={orAbsent(found.operation)} />
        </span>
      )),
    },
    {
      label: "Symbol",
      value: fact((found) => (
        <span className="font-mono">
          <Formatted value={orAbsent(found.symbol)} />
        </span>
      )),
    },
    {
      label: "SDK version",
      value: fact((found) => (
        <span className="font-mono">
          <Formatted value={orAbsent(found.sdk_version)} />
        </span>
      )),
    },
    {
      label: "This finding's rung",
      value: fact((found) => <RungBadge rung={found.finding.binding_source} />),
    },
    { label: "Remediation", value: remediationFact(remediation) },
  ]
}

export interface FindingPageProps {
  readonly question?: string
}

export function FindingPage({ question = DEFAULT_QUESTION }: FindingPageProps) {
  // A URL is user input, so the identifier is checked here rather than assumed. The query
  // lives one level down so that check happens before a request is made for it.
  // `repoId` arrives because every route is workspace-scoped as of `M14-W386`. Links built
  // without it resolved to the collapsed region's old addresses and rendered
  // "No screen at this address." -- caught by opening the screen rather than by a type error,
  // because a path is a string and every one of these compiled perfectly.
  const { repoId, findingId } = useParams<{ repoId: string; findingId: string }>()
  if (findingId === undefined) return <UnknownRoute />
  return <FindingDetailPage repoId={repoId} findingId={findingId} question={question} />
}

function FindingDetailPage({
  repoId,
  findingId,
  question,
}: {
  repoId: string | undefined
  findingId: string
  question: string
}) {
  const query = useFinding(findingId)
  const run = useWorkflow(findingId)
  const remediation = describeRemediation({
    data: run.data,
    missing: run.isError && run.error instanceof NotFoundError,
    failed: run.isError,
  })

  // Short, because it renders once per fact and the panel beside the rail carries the same answer
  // in full: five rows spelling out that panel's sentence would be one fact written six times.
  const failure = query.isError ? (
    query.error instanceof NotFoundError ? (
      <Absent>this finding is not open</Absent>
    ) : (
      <Absent>the API did not answer</Absent>
    )
  ) : null

  const trail = [
    { label: "Repositories", to: "/" },
    ...(query.isSuccess
      ? [
          {
            label: query.data.vendor,
            to: `/vendors/${encodeURIComponent(query.data.vendor)}`,
          },
        ]
      : []),
    { label: formatFindingBadge(findingId) },
  ]

  const title = query.isSuccess ? (
    <DetailTitleText title={findingTitle(query.data.vendor, query.data.operation)} />
  ) : failure !== null ? (
    failure
  ) : (
    <Pending />
  )

  return (
    <DetailGrid
      /* Content left, rail right, which is what `screens/06-finding.png` draws. This screen
         shipped inverted on `M7-W178`'s argument that a detail has one subject so the facts
         come first, and the settled authority order resolves the disagreement rather than my
         taste: the mock is authority 3 for layout, a port's own reasoning is 4, and no
         decision covers which side a rail sits on. One prop, so it reverses in one line. */
      railSide="end"
      header={
        <PageHeader
          trail={<Breadcrumbs trail={trail} />}
          title={title}
          question={question}
          /* The mock draws one primary action on the header row, right of the title, and this
             screen had none — its destinations were prose links down in the rail. Ported as the
             arrangement rather than as the label: the mock's button says "Review proposed patch"
             unconditionally, and this one exists only when a run actually reached a pull request,
             because a button offering to review a patch that was never opened is the kind of
             claim the rest of this console spends six screens refusing. */
          actions={
            reachedPullRequest(remediation) ? (
              <Button asChild>
                <Link to={`${workspacePath(repoId)}/findings/${encodeURIComponent(findingId)}/workflow/pull-request`}>
                  Review proposed patch
                </Link>
              </Button>
            ) : undefined
          }
        />
      }
      rail={
        <div className="flex min-w-0 flex-col gap-section">
          <FactList
            facts={findingFacts(repoId, findingId, query.isSuccess ? query.data : null, failure, remediation)}
          />
          <p className="text-body text-ink-muted">
            What this call site calls, and how the system knows it does.
          </p>

          {/* Outside the success branch on purpose. A finding that has been patched or
              abandoned is no longer open, so this page 404s for it — and that is exactly the
              finding whose run is most worth reading. The workflow lives in the checkpointer,
              which does not care whether the graph still holds the finding, so both links below
              can be live on a page whose finding is gone. */}
          {/* The mock draws these two destinations as stacked, full-width controls rather than
              as sentences with a link inside them, and that is the arrangement ported here: a
              reader scanning a rail for somewhere to go finds a control at a glance and has to
              read a paragraph to find a link.

              **Every sentence stays.** The ruling is that where the drawn layout has no room for
              a sentence the layout gets the room, not the sentence gets cut — so each caption
              keeps its full wording underneath its control instead of being folded into a label
              or moved into a tooltip. */}
          <div className="flex flex-col gap-field">
            <div className="flex flex-col gap-field">
              <Button asChild variant="outline" className="w-full justify-start">
                <Link to={`${workspacePath(repoId)}/findings/${encodeURIComponent(findingId)}/workflow`}>
                  Open the solution workflow
                </Link>
              </Button>
              <p className="text-body text-ink-muted">
                What Sync did about this finding, node by node.
              </p>
            </div>
            {reachedPullRequest(remediation) && (
              <div className="flex flex-col gap-field">
                <Button asChild variant="outline" className="w-full justify-start">
                  <Link to={`${workspacePath(repoId)}/findings/${encodeURIComponent(findingId)}/workflow/pull-request`}>
                    Pull request
                  </Link>
                </Button>
                <p className="text-body text-ink-muted">
                  The evidence bundle behind the patch this run opened.
                </p>
              </div>
            )}
          </div>
        </div>
      }
    >
      <div className="flex min-w-0 flex-col gap-8">
        {query.isPending && <LoadingState what={`finding ${findingId}`} />}

        {query.isError &&
          (query.error instanceof NotFoundError ? (
            <NotFoundState
              headline="That finding is not open."
              detail="The API answered, and the graph holds no open finding with this identifier. It may have been patched, abandoned, or it may never have existed. This is an answer about the finding, not a failure of the console."
              identifier={query.error.identifier}
            />
          ) : (
            <ErrorState error={query.error} what={`finding ${findingId}`} onRetry={() => void query.refetch()} />
          ))}

        {query.isSuccess && (
          <>
            <MetricPanel
              label="Known changes"
              caption="Vendor changes naming this call site, shallow. The full record is fetched by identifier."
            >
              {query.data.known_changes.length === 0 ? (
                <EmptyState
                  headline="No vendor change names this call site."
                  detail="The finding was raised by something other than a spec diff."
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
                    {query.data.known_changes.map((change) => (
                      <TableRow key={change.change_id}>
                        <TableCell className="font-mono">{change.change_id}</TableCell>
                        <TableCell>{change.kind}</TableCell>
                        <TableCell>{change.severity}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </MetricPanel>

            <MetricPanel
              label="What the call site touches"
              caption="The argument keys sent and the response fields read — the surface a change has to break for this finding to matter."
            >
              <FieldList label="Argument keys" values={query.data.args_keys} />
              <FieldList label="Response fields read" values={query.data.response_fields_read} />
            </MetricPanel>

            <MetricPanel
              label="Provenance"
              caption="Where this answer came from. The rung in the facts beside this is the column on this one finding and always says something definite; the rung below describes the whole answer, which is built from every finding naming this call site."
            >
              <ProvenanceStrip
                provenance={query.data}
                bindingNullLabel="mixed: more than one detector names this call site and they disagree on the rung — this finding's own rung is in the facts beside this panel"
              />
            </MetricPanel>
          </>
        )}
      </div>
    </DetailGrid>
  )
}
