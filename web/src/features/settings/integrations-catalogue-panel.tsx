/**
 * Settings → Integrations: every integration this deployment can watch, listed so a reader
 * learns what exists rather than discovering it in documentation.
 *
 * The catalogue lesson from the reference read
 * (`references/notes/nango-integration-architecture.md`): a catalogue-scale product lists its
 * whole surface, and adding to it is a configuration entry rather than a code change. Ours is
 * the adapter registry — coded adapters, the generated tier's YAML, watched MCP servers.
 *
 * **Three states, three different facts, and no fourth invented.** `watched` — this codebase
 * calls it and the index bound a call site. `staged` — a specification is on disk, so a scan
 * could bind one today. `available` — registered and neither, the ordinary state of an
 * integration this codebase does not use.
 *
 * **There is no connect button, and that is the product rather than a gap.** Sync watches an
 * API by reading its published specification and the customer's own code; it holds no vendor
 * credential and never calls a vendor. So each row says what it would take — import the SDK
 * this vendor publishes, and index — instead of offering an OAuth flow this product does not
 * have and does not want.
 */

import { useQuery } from "@tanstack/react-query"

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { AdapterTierTag } from "@/components/tag"
import { InfoHint } from "@/components/info-hint"
import { ErrorState, LoadingState } from "@/components/states"
import { type CatalogueRow, fetchCatalogue } from "@/features/vendors/catalogue"

const STATE_WORD: Record<CatalogueRow["state"], string> = {
  watched: "in use here",
  staged: "staged",
  available: "available",
}

function packages(row: CatalogueRow): string {
  const names = Object.entries(row.sdk_bindings).map(([language, binding]) => {
    const name = binding.package ?? binding.distribution ?? binding.module
    return `${language}: ${name}`
  })
  return names.join(" · ")
}

export function IntegrationsCataloguePanel({ repoId }: { repoId: string }) {
  const query = useQuery({
    queryKey: ["integrations-catalogue", repoId],
    queryFn: ({ signal }) => fetchCatalogue(repoId, signal),
  })

  if (query.isPending) return <LoadingState what="the integrations catalogue" />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what="the integrations catalogue"
        onRetry={() => void query.refetch()}
      />
    )
  }

  const { integrations, by_tier, by_state, total } = query.data

  return (
    <div className="flex flex-col gap-section">
      <div className="flex flex-col gap-field border-b border-line pb-field">
        <div className="flex items-center gap-row">
          <h2 className="text-emphasis font-medium text-ink">Integrations</h2>
          <InfoHint label="About the integrations catalogue">
            Every integration this deployment can watch. Sync watches an API by reading its
            published specification and your code — it holds no vendor credential and never
            calls a vendor — so an integration becomes active when your codebase imports its
            SDK and an index pass finds the call, not when you sign in to it. Adding one is a
            configuration entry: coded adapters live in this repository, the generated tier in{" "}
            <span className="font-mono">generated-vendors.yaml</span>.
          </InfoHint>
        </div>
        <p className="max-w-prose text-body text-ink-muted">
          {total} registered — {by_state.watched ?? 0} in use in this codebase,{" "}
          {by_state.staged ?? 0} staged and ready to bind, {by_state.available ?? 0} available.
          By tier: {Object.entries(by_tier).map(([tier, count]) => `${count} ${tier}`).join(", ")}.
        </p>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Integration</TableHead>
            <TableHead>State</TableHead>
            <TableHead>Tier</TableHead>
            <TableHead>SDK packages</TableHead>
            <TableHead>Specification</TableHead>
            <TableHead>Changes</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {integrations.map((row) => (
            <TableRow key={row.vendor_id}>
              <TableCell className="font-mono">{row.vendor_id}</TableCell>
              <TableCell>
                <span className="furniture rounded-control border border-line px-field py-field text-meta text-ink-muted">
                  {STATE_WORD[row.state]}
                </span>
                {row.call_sites > 0 && (
                  <span className="ml-row text-meta text-ink-muted tabular-nums">
                    {row.call_sites} call sites
                  </span>
                )}
              </TableCell>
              <TableCell>
                <AdapterTierTag tier={row.tier} />
              </TableCell>
              <TableCell className="font-mono text-meta text-ink-muted">
                {packages(row) || "—"}
              </TableCell>
              <TableCell className="font-mono text-meta text-ink-muted">
                {row.staged === null
                  ? "not staged"
                  : `${row.staged.tag ?? "staged"}${row.staged.symbols ? ` · ${row.staged.symbols} symbols` : ""}`}
              </TableCell>
              <TableCell className="font-mono text-meta text-ink-muted tabular-nums">
                {row.changes_recorded.toLocaleString()}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <p className="max-w-prose text-meta text-ink-muted">
        An integration listed <span className="font-mono">available</span> is registered and
        unused here — it becomes <span className="font-mono">in use</span> when this codebase
        imports its SDK and an index pass finds the call. Nothing on this screen connects an
        account, because Sync never holds one.
      </p>
    </div>
  )
}
