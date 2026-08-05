/**
 * One finding: the binding in full, and the vendor changes that name it.
 *
 * Two rungs on one screen, and they answer different questions. `finding.binding_source` is
 * this finding's own column and always says something definite — it is what a false positive
 * here has to be attributable to. The envelope's rung describes the whole answer, which is
 * built from every finding naming this call site, and goes null when those disagree. Showing
 * only the envelope's would lose the definite value at the exact moment it matters.
 */

import { Link, useParams } from "react-router"

import { NotFoundError } from "@/api/errors"
import { useFinding } from "@/api/queries"
import { ProvenanceStrip, RungBadge } from "@/components/provenance"
import { ErrorState, LoadingState, NotFoundState } from "@/components/states"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { ABSENT, orAbsent } from "@/lib/format"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { UnknownRoute } from "@/layouts/unknown-route"

function FieldList({ label, values }: { label: string; values: string[] }) {
  return (
    <div className="flex flex-col gap-1">
      <h3 className="text-meta tracking-wide text-muted-foreground uppercase">{label}</h3>
      {values.length === 0 ? (
        <p className="text-body text-muted-foreground">{ABSENT} none recorded</p>
      ) : (
        <ul className="flex flex-wrap gap-2">
          {values.map((value) => (
            <li key={value} className="rounded border border-border px-1.5 py-0.5 font-mono text-meta">
              {value}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function FindingPage() {
  // A URL is user input, so the identifier is checked here rather than assumed. The query
  // lives one level down so that check happens before a request is made for it.
  const { findingId } = useParams<{ findingId: string }>()
  if (findingId === undefined) return <UnknownRoute />
  return <FindingDetail findingId={findingId} />
}

function FindingDetail({ findingId }: { findingId: string }) {
  const query = useFinding(findingId)

  const trail = [
    { label: "Fleet", to: "/" },
    { label: "Codebase", to: "/codebase" },
    ...(query.isSuccess
      ? [
          {
            label: query.data.vendor,
            to: `/vendors/${encodeURIComponent(query.data.vendor)}`,
          },
        ]
      : []),
    { label: findingId },
  ]

  return (
    <section className="flex flex-col gap-4">
      <Breadcrumbs trail={trail} />
      <h1 className="font-mono text-page">{findingId}</h1>

      {/* Outside the success branch on purpose. A finding that has been patched or
          abandoned is no longer open, so this page 404s for it — and that is exactly the
          finding whose run is most worth reading. The workflow lives in the checkpointer,
          which does not care whether the graph still holds the finding. */}
      <p className="text-body">
        <Link
          to={`/findings/${encodeURIComponent(findingId)}/workflow`}
          className="underline underline-offset-2"
        >
          Solution workflow
        </Link>{" "}
        <span className="text-muted-foreground">
          — what Sync did about this finding, node by node.
        </span>
      </p>

      {query.isPending && <LoadingState what={`finding ${findingId}`} />}

      {query.isError &&
        (query.error instanceof NotFoundError ? (
          <NotFoundState
            headline="That finding is not open."
            detail="The API answered, and the graph holds no open finding with this identifier. It may have been patched, abandoned, or it may never have existed. This is an answer about the finding, not a failure of the console."
            identifier={query.error.identifier}
          />
        ) : (
          <ErrorState error={query.error} what={`finding ${findingId}`} />
        ))}

      {query.isSuccess && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Binding</CardTitle>
              <CardDescription>
                What this call site calls, and how the system knows it does.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div>
                  <dt className="text-meta tracking-wide text-muted-foreground uppercase">
                    Vendor
                  </dt>
                  <dd className="font-mono text-body">
                    <Link
                      to={`/vendors/${encodeURIComponent(query.data.vendor)}`}
                      className="underline underline-offset-2"
                    >
                      {query.data.vendor}
                    </Link>
                  </dd>
                </div>
                <div>
                  <dt className="text-meta tracking-wide text-muted-foreground uppercase">
                    Operation
                  </dt>
                  <dd className="font-mono text-body">{orAbsent(query.data.operation)}</dd>
                </div>
                <div>
                  <dt className="text-meta tracking-wide text-muted-foreground uppercase">
                    Symbol
                  </dt>
                  <dd className="font-mono text-body">{orAbsent(query.data.symbol)}</dd>
                </div>
                <div>
                  <dt className="text-meta tracking-wide text-muted-foreground uppercase">
                    SDK version
                  </dt>
                  <dd className="font-mono text-body">{orAbsent(query.data.sdk_version)}</dd>
                </div>
                <div>
                  <dt className="text-meta tracking-wide text-muted-foreground uppercase">
                    This finding's rung
                  </dt>
                  <dd className="text-body">
                    <RungBadge rung={query.data.finding.binding_source} />
                  </dd>
                </div>
              </dl>
              <ProvenanceStrip
                provenance={query.data}
                bindingNullLabel="mixed: more than one detector names this call site and they disagree on the rung — this finding's own rung is above"
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>What the call site touches</CardTitle>
              <CardDescription>
                The argument keys sent and the response fields read — the surface a change
                has to break for this finding to matter.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <FieldList label="Argument keys" values={query.data.args_keys} />
              <FieldList
                label="Response fields read"
                values={query.data.response_fields_read}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Known changes</CardTitle>
              <CardDescription>
                Vendor changes naming this call site, shallow. The full record is fetched by
                identifier.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {query.data.known_changes.length === 0 ? (
                <p className="text-body text-muted-foreground">
                  {ABSENT} No vendor change names this call site. The finding was raised by
                  something other than a spec diff.
                </p>
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
                        <TableCell className="font-mono">
                          {change.change_id}
                        </TableCell>
                        <TableCell>{change.kind}</TableCell>
                        <TableCell>{change.severity}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </section>
  )
}
