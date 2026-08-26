/**
 * One published change, opened: what it names, what compared it, and what it meets here.
 *
 * Everything a reader does not need while scanning the feed lives here — the version pair, the
 * pointer into the document the diff walked, and the full form of the binding answer with the way
 * through to the surface that joins the two halves.
 */

import { Link } from "react-router"

import { FactList } from "@/components/fact-list"
import { RelativeTime } from "@/components/relative-time"
import { Absent } from "@/components/status"
import { ChangeKindTag, SeverityTag } from "@/components/tag"
import type { ChangeBinding } from "@/features/vendors/change-binding"
import type { ChangeRow } from "@/features/vendors/changes-feed"
import { bindingSurfaceHref } from "@/lib/hrefs"

/** The claim about this codebase, in full — the drawer's room for the sentence the cell cannot hold. */
function BindingParagraph({
  binding,
  repoId,
  change,
}: {
  binding: ChangeBinding
  repoId: string
  change: ChangeRow
}) {
  if (binding.kind === "bound") {
    return (
      <p className="max-w-prose text-body text-ink-muted">
        <span className="text-ink">
          {binding.callSites.toLocaleString()} current call site
          {binding.callSites === 1 ? "" : "s"} in {repoId}
        </span>{" "}
        name <span className="font-mono">{change.operation_id}</span>. That is static evidence from
        the last index pass, not observed traffic. Whether any of them breaks is a finding, which
        the binding surface below is where to read.
      </p>
    )
  }
  if (binding.kind === "not-bound") {
    return (
      <p className="max-w-prose text-body text-ink-muted">
        <span className="text-ink">No current call site in {repoId} names this operation.</span>{" "}
        The census answered and holds none — a measured zero rather than an unasked question. The
        change is still real; it lands somewhere this codebase does not reach.
      </p>
    )
  }
  if (binding.kind === "never-indexed") {
    return (
      <p className="max-w-prose text-body text-ink-muted">
        <span className="text-ink">{repoId} has never been indexed.</span> No call site was looked
        for, so nothing here says this operation is unused — only that nobody has checked.
      </p>
    )
  }
  return (
    <p className="max-w-prose text-body text-ink-muted">
      <span className="text-ink">Not counted.</span> {binding.why}. Until it can, an absence here
      would be a claim nothing measured.
    </p>
  )
}

export function ChangeInspector({
  change,
  binding,
  repoId,
}: {
  change: ChangeRow
  binding: ChangeBinding
  repoId: string
}) {
  return (
    <div className="flex min-w-0 flex-col gap-section">
      <section className="flex min-w-0 flex-col gap-row">
        <h3 className="furniture text-meta text-ink-muted">Does this codebase call it</h3>
        <BindingParagraph binding={binding} repoId={repoId} change={change} />
        <Link
          to={bindingSurfaceHref(repoId, change.vendor_id, change.operation_id)}
          className="text-body underline underline-offset-2"
        >
          Open the binding surface for {change.vendor_id} / {change.operation_id}
        </Link>
      </section>

      <section className="flex min-w-0 flex-col gap-row">
        <h3 className="furniture text-meta text-ink-muted">What the vendor published</h3>
        <FactList
          facts={[
            { label: "Integration", value: <span className="font-mono">{change.vendor_id}</span> },
            { label: "Operation", value: <span className="font-mono break-all">{change.operation_id}</span> },
            { label: "Severity as published", value: <SeverityTag severity={change.severity} /> },
            { label: "Change kind", value: <ChangeKindTag kind={change.kind} /> },
            {
              label: "Versions compared",
              value: (
                <span className="font-mono break-all">
                  {change.from_version} → {change.to_version}
                </span>
              ),
            },
            {
              label: "Document pointer",
              value:
                change.path_ptr === "" ? (
                  <Absent>no pointer recorded</Absent>
                ) : (
                  <span className="font-mono break-all">{change.path_ptr}</span>
                ),
            },
            {
              label: "Detected",
              value: <RelativeTime iso={change.detected_at} />,
            },
            { label: "Source", value: <span className="font-mono">{change.source}</span> },
          ]}
        />
        <p className="max-w-prose text-meta text-ink-muted">
          Detected is when Sync noticed, never when the vendor shipped — nothing in the graph
          carries a publication date.
          {change.source === "oasdiff" && (
            <>
              {" "}
              <span className="text-ink">This row came from oasdiff</span>, which returns a
              different answer between runs over identical bytes: it is at-least-once rather than
              converged, so a count over rows like this one is not a measurement of how much the
              vendor changed.
            </>
          )}
        </p>
      </section>
    </div>
  )
}
