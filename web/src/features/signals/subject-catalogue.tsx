/**
 * The vendor role's catalogue: one card per vendor this repository's code calls.
 *
 * `docs/superpowers/briefs/2026-08-07-substrate-signals.md` is the mapping table this port was
 * gated on, and its ruling 6 is why this exists beside `features/repositories/index-coverage-card.tsx`
 * rather than inside it. Both read `GET /api/repositories/{repo_id}/coverage` and both are honest
 * readings of `by_vendor`; the two levels ask different questions of it. Codebase asks how much of
 * this codebase the index has read, and answers with a table. Signals asks which vendor subjects
 * are attached to this repository's graph, and a subject is a card.
 *
 * **Neither rendering computes anything, which is what makes two of them affordable.** `by_vendor`
 * is already the whole answer — not a page — so the catalogue is a sort and a join, and
 * `attachedVendors` is the one place either happens. What could drift between the two screens is
 * wording, so the two sentences that carry a claim are reproduced here in full rather than
 * paraphrased: a vendor absent from this catalogue is a question rather than a zero, and "last
 * indexed" is staleness rather than a promise.
 *
 * The total is stated in words in the caption rather than at the figure register. Each card already
 * carries its own count there, and a figure that is the sum of the figures directly beneath it is
 * one fact at two weights.
 *
 * **The exported component is named for what the role's members are rather than for the payload's
 * key, and that is a constraint rather than a preference.** The M5 table's relationship sentence for
 * this role is "A subject. Code calls it; it can break you."
 * `tests/test_console_signals_roles.py` requires the page to read every role name out of
 * `roles.ts` and forbids one appearing literally in `signals-page.tsx` — an import spelling the
 * role's own noun would put that name back in the file the guard exists to keep clean. The
 * derivation below keeps the payload's noun, because nothing imports it into the page.
 */

import { Link } from "react-router"

import { useRepositoryCoverage } from "@/api/queries"
import type { IndexCoverageResponse } from "@/api/types"
import { Formatted } from "@/components/status"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { formatTimestamp } from "@/lib/format"
import { Card, CardContent, CardHeader } from "@/vendor/supabase/ui/card"

import { vendorHref } from "@/lib/hrefs"
export interface AttachedVendor {
  vendorId: string
  callSites: number
  /** Absent when the payload carries no timestamp for this vendor — see the card below. */
  lastIndexed: string | undefined
}

/**
 * The catalogue's rows, in vendor-name order.
 *
 * Ordered here rather than left to the payload because an object's key order is a serialisation
 * detail: a catalogue that reshuffles between deploys is one nobody can scan twice.
 */
export function attachedVendors(coverage: IndexCoverageResponse): AttachedVendor[] {
  return Object.entries(coverage.by_vendor)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([vendorId, callSites]) => ({
      vendorId,
      callSites,
      // Optional access, not the type contract: `last_indexed` shares `by_vendor`'s key set by
      // construction on every current build of `index_coverage`. The guard is here only because
      // the console's own dev API process can be older than the code it is serving while a deploy
      // is mid-flight, and a stale response must not crash the page that reads it.
      lastIndexed: coverage.last_indexed?.[vendorId],
    }))
}

function SubjectCard({ vendor, repoId }: { vendor: AttachedVendor; repoId: string }) {
  return (
    <Card className="flex min-w-0 flex-col">
      <CardHeader>
        {/* `h3` under the role group's `h2`: a catalogue card is contained by its role, and an
            outline that skipped the level would leave the cards siblings of the roles. */}
        <h3>
          <Link
            to={vendorHref(repoId, vendor.vendorId)}
            className="font-mono text-emphasis break-words underline underline-offset-2"
          >
            {vendor.vendorId}
          </Link>
        </h3>
      </CardHeader>
      <CardContent className="flex flex-col gap-section">
        <p className="flex flex-wrap items-baseline gap-row">
          <span className="text-figure text-foreground">{vendor.callSites.toLocaleString()}</span>
          <span className="text-body text-muted-foreground">
            call site{vendor.callSites === 1 ? "" : "s"} indexed
          </span>
        </p>
        <div className="flex flex-col gap-field">
          <span className="furniture text-meta text-ink-muted">Last indexed</span>
          <span className="font-mono text-meta break-words">
            <Formatted value={formatTimestamp(vendor.lastIndexed)} />
          </span>
        </div>
      </CardContent>
    </Card>
  )
}

export function SubjectCatalogue({ repoId }: { repoId: string }) {
  const query = useRepositoryCoverage(repoId)

  if (query.isPending) return <LoadingState what={`index coverage for ${repoId}`} />
  if (query.isError) {
    return <ErrorState error={query.error} what={`index coverage for ${repoId}`} onRetry={() => void query.refetch()} />
  }

  const vendors = attachedVendors(query.data)

  return (
    <div className="flex min-w-0 flex-col gap-section">
      <p className="max-w-prose text-body text-muted-foreground">
        {/* The count leads only when there is one. With nothing attached the empty state beneath
            says so in its own words, and a "0 vendors, across 0 call sites" opening would be the
            same nothing stated twice, less well the first time. */}
        {vendors.length > 0 && (
          <>
            {vendors.length === 1 ? "One vendor is" : `${vendors.length} vendors are`} attached to
            this repository, across {query.data.total_call_sites.toLocaleString()} call site
            {query.data.total_call_sites === 1 ? "" : "s"} the index holds for it.{" "}
          </>
        )}
        A vendor absent from this catalogue is not zero — it is a question this view cannot answer:
        whether the indexer looked and found nothing, or nothing declares which package to look for.
        A vendor name below opens that vendor's own page with this repository's scope carried into
        it, so the findings there are this codebase's; what the vendor published is not scoped, and
        that page says which of its two halves is which.
      </p>
      {vendors.length === 0 ? (
        <EmptyState
          headline={`The index holds no call site for ${repoId}.`}
          detail="This repository was never indexed, or it was indexed and nothing bound to a vendor was found. Those are the same answer here: the index has no configuration table, so a repository it has never seen a call site from is indistinguishable from one nobody ever configured."
        />
      ) : (
        <>
          <div className="grid auto-rows-fr gap-section sm:grid-cols-2 xl:grid-cols-3">
            {vendors.map((vendor) => (
              <SubjectCard key={vendor.vendorId} vendor={vendor} repoId={repoId} />
            ))}
          </div>
          <p className="max-w-prose text-body text-muted-foreground">
            "Last indexed" is the newest indexing timestamp among that vendor's call sites —
            staleness, not a promise the index is current. A repository re-scanned weeks ago reports
            the same value every day after, until another re-index moves it.
          </p>
        </>
      )}
    </div>
  )
}
