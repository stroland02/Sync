/**
 * One binding, drawn: the call site, the operation it binds to, and what the vendor changed.
 *
 * `docs/superpowers/briefs/2026-08-07-substrate-binding-surface.md` is the mapping table this port
 * was gated on, and rulings 8 through 12 are this file. Read those before changing what is drawn
 * here.
 *
 * **This is a drawing of one binding and never of a fleet of them.** Task 11 refused a bipartite
 * diagram of call sites against operations on cardinality, and that refusal is not reopened: a
 * diagram of two thousand edges cannot be read, which is why `features/fleet/cardinality.tsx`
 * renders a sentence about a set that large instead. At cardinality one nothing is elided, nothing
 * is sampled, and there is no threshold past which the picture stops being true — so this is the
 * counter-example rather than the exception.
 *
 * It is composed cards with the relationship stated in words between them. No canvas, no plotted
 * SVG, no graph library, no new dependency: a card per node and a ruled line per edge is the whole
 * mechanism, which is also why it survives at whatever width the drawer takes.
 *
 * **Each edge states its rung, and the edge that has none says so.** The call site binds to the
 * operation on that row's own rung, consumed from `components/provenance.tsx` and never
 * re-derived. The vendor change does not bind to anything — it is evidence about the vendor rather
 * than about this codebase — and an edge left silently bare would read as a missing value rather
 * than as the distinction it is.
 *
 * **A key this page does not hold is its own answer.** A binding address is shareable, which is
 * most of the reason it is in the URL; the reader who opens one may be under a filter the sender
 * did not have, or on another page. Rendering the list with no drawer would tell them their link
 * was wrong and rendering an empty drawer would tell them the call site was gone. Neither is a
 * claim this payload supports, so the drawer opens and says which it cannot tell.
 */

import { useRef, type ReactNode } from "react"
import { Link } from "react-router"

import type { BindingChange, BindingSurfaceResponse } from "@/api/types"
import { FactList } from "@/components/fact-list"
import { RungBadge } from "@/components/provenance"
import { Formatted } from "@/components/status"
import { formatTimestamp, orAbsent } from "@/lib/format"
import type { BindingSelection } from "@/features/bindings/binding-selection"
import { joinOrAbsent } from "@/features/bindings/call-site-fields"
import { Card, CardContent, CardHeader } from "@/vendor/supabase/ui/card"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetSection,
  SheetTitle,
} from "@/vendor/supabase/ui/sheet"

/** One node of the drawing. The label is scanned, so it takes the furniture register. */
function Node({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Card className="flex min-w-0 flex-col">
      <CardHeader>
        <h3 className="furniture text-meta text-ink-muted">{label}</h3>
      </CardHeader>
      <CardContent className="flex flex-col gap-field">{children}</CardContent>
    </Card>
  )
}

/**
 * One edge, stated rather than plotted.
 *
 * The rule down the left is what makes the two cards it sits between read as connected. It is a
 * hairline in the same token every other rule on this console draws, not a diagram element.
 */
function Edge({ children }: { children: ReactNode }) {
  return (
    <div className="ml-section border-l border-line py-field pl-section">
      <p className="max-w-prose text-body text-muted-foreground">{children}</p>
    </div>
  )
}

function ChangeNode({ change }: { change: BindingChange }) {
  return (
    <Node label="Vendor change">
      <FactList
        facts={[
          { label: "Kind", value: change.kind },
          { label: "Severity", value: change.severity },
          {
            label: "Path",
            value: (
              <span className="font-mono">
                <Formatted value={orAbsent(change.path_ptr)} />
              </span>
            ),
          },
          {
            label: "Versions",
            value: (
              <span className="font-mono">
                <Formatted value={orAbsent(change.from_version)} /> →{" "}
                <Formatted value={orAbsent(change.to_version)} />
              </span>
            ),
          },
          {
            label: "Detected",
            value: (
              <span className="font-mono">
                <Formatted value={formatTimestamp(change.detected_at)} />
              </span>
            ),
          },
        ]}
      />
    </Node>
  )
}

function OneBinding({
  selection,
  data,
}: {
  selection: Extract<BindingSelection, { kind: "resolved" }>
  data: BindingSurfaceResponse
}) {
  const site = selection.site
  const changes = data.changes.items
  const paged = data.changes.total > changes.length

  return (
    <>
      <Node label="Call site">
        <FactList
          facts={[
            { label: "Repository", value: <span className="font-mono">{site.repo_id}</span> },
            // The whole path, not `pathAfter`'s remainder. The table shortens it because the
            // shared prefix is identical on every row and the column has eight columns ahead of
            // it; a drawer holding one row has neither problem.
            { label: "Path", value: <span className="font-mono break-words">{site.path}</span> },
            {
              label: "Line and column",
              value: (
                <span className="font-mono">
                  {site.line}:{site.col}
                </span>
              ),
            },
            {
              label: "Symbol",
              value: (
                <span className="font-mono break-words">
                  <Formatted value={orAbsent(site.symbol)} />
                </span>
              ),
            },
            {
              label: "SDK version",
              value: (
                <span className="font-mono">
                  <Formatted value={orAbsent(site.sdk_version)} />
                </span>
              ),
            },
            {
              label: "Argument keys",
              value: (
                <span className="font-mono break-words">
                  <Formatted value={joinOrAbsent(site.args_keys)} />
                </span>
              ),
            },
            {
              label: "Response fields read",
              value: (
                <span className="font-mono break-words">
                  <Formatted value={joinOrAbsent(site.response_fields_read)} />
                </span>
              ),
            },
            { label: "Loop depth", value: <span className="font-mono">{site.loop_depth}</span> },
            {
              label: "Indexed at",
              value: (
                <span className="font-mono">
                  <Formatted value={formatTimestamp(site.indexed_at)} />
                </span>
              ),
            },
          ]}
        />
      </Node>

      <Edge>
        This call site binds to the operation below on the <RungBadge rung={site.binding_rung} />{" "}
        rung: the row's own value, and it says which class of evidence established the binding
        rather than how much to trust it. Nothing on this page mixes rungs — every call site here
        is what the index found by reading the source.
      </Edge>

      <Node label="Operation">
        <FactList
          facts={[
            {
              label: "Vendor",
              value: (
                <Link
                  to={`/vendors/${encodeURIComponent(data.vendor_id)}${
                    data.repo_id === null ? "" : `?repo_id=${encodeURIComponent(data.repo_id)}`
                  }`}
                  className="font-mono break-words underline underline-offset-2"
                >
                  {data.vendor_id}
                </Link>
              ),
            },
            {
              label: "Operation",
              value: <span className="font-mono break-words">{data.operation_id}</span>,
            },
          ]}
        />
      </Node>

      <Edge>
        {changes.length === 0
          ? "The vendor has never changed this operation, so there is no third node to draw. That is an answer about the ingested feeds and not a failure — nothing here says the operation is safe, only that no feed has named a change against it."
          : "The vendor changed the operation above. That edge carries no rung, and the absence is the point: a vendor change is evidence about the vendor rather than about this codebase, so nothing in it was read out of your source. Whether this call site is affected by it is a detector's answer, and a detector's answer is a finding rather than an edge."}
      </Edge>

      {changes.map((change) => (
        <ChangeNode key={change.change_id} change={change} />
      ))}

      {paged && (
        <p className="max-w-prose text-body text-muted-foreground">
          {changes.length} of {data.changes.total.toLocaleString()} changes are drawn here — the
          rest are on later pages of the table behind this drawer. The count above the table is the
          operation's; this one is the page's.
        </p>
      )}
    </>
  )
}

/**
 * The URL named a call site and this page does not hold it.
 *
 * Not an `EmptyState`: that component means the API answered and the answer was nothing. The API
 * answered with rows here — this window over them does not include the one the address asked for,
 * which is a fact about the address and the filters rather than about the graph.
 */
function UnheldBinding({ bindingKey, held }: { bindingKey: string; held: number }) {
  return (
    <div className="flex flex-col gap-field">
      <p className="font-mono text-meta break-words">{bindingKey}</p>
      <p className="max-w-prose text-body text-muted-foreground">
        A binding address names a call site by repository, path, line and column. This page holds{" "}
        {held.toLocaleString()} call {held === 1 ? "site" : "sites"} and none of them is that one —
        which could mean a filter above excludes it, that it is on another page, or that the index
        holds no such call site at all. Nothing here can tell those apart, so none is picked: clear
        the filters and return to the first page, and if it is still not listed then this operation
        has no such binding.
      </p>
    </div>
  )
}

export function BindingDrawer({
  selection,
  data,
  onClose,
}: {
  selection: BindingSelection
  data: BindingSurfaceResponse
  onClose: () => void
}) {
  // Radix keeps the content mounted through the closing transition, so rendering straight off
  // `selection` would swap the drawing for an empty panel for the three hundred milliseconds the
  // sheet takes to leave — the reader would watch their binding vanish before the drawer did. The
  // last open selection is what is drawn while it closes. Null only before the drawer has ever
  // opened, when Radix has mounted nothing at all.
  const lastOpen = useRef<Exclude<BindingSelection, { kind: "none" }> | null>(null)
  if (selection.kind !== "none") lastOpen.current = selection
  const shown = lastOpen.current
  const site = shown?.kind === "resolved" ? shown.site : null

  return (
    <Sheet
      open={selection.kind !== "none"}
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
    >
      <SheetContent side="right" size="lg" className="flex flex-col overflow-y-auto">
        <SheetHeader>
          {/* Mono where the title is an identifier and not where it is a sentence: a sentence set
              in mono reads as a value the payload carries. */}
          <SheetTitle className={site === null ? "text-emphasis" : "font-mono break-words text-emphasis"}>
            {site === null ? (
              "This page does not hold that call site."
            ) : (
              <>
                {site.path}:{site.line}:{site.col}
              </>
            )}
          </SheetTitle>
          <SheetDescription>
            {site === null
              ? "The address carries a binding this window over the call sites does not include."
              : // No node count in this sentence: an operation the vendor has never changed has no
                // third node, and a description promising one would be wrong on that branch.
                "One binding, drawn: the call site, the operation it binds to, and what the vendor changed about that operation. A node is a row this payload carries, and an edge says what it rests on."}
          </SheetDescription>
        </SheetHeader>
        <SheetSection className="flex flex-col gap-section">
          {shown === null ? null : shown.kind === "resolved" ? (
            <OneBinding selection={shown} data={data} />
          ) : (
            <UnheldBinding bindingKey={shown.key} held={data.call_sites.items.length} />
          )}
        </SheetSection>
      </SheetContent>
    </Sheet>
  )
}
