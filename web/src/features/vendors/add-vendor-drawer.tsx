/**
 * "Add a vendor", said honestly: two different additions, and neither of them happens here.
 *
 * ## Why this is a panel of text and not a form
 *
 * The API this console reads is read-only — `test_no_route_reaches_past_the_read_surface` holds
 * that behaviourally, and `.claude/rules/console-dev-loop.md` records the one route that exists
 * and is deliberately not called. So there is no POST to put behind a submit button, and a form
 * that looked like one would be the console claiming an act it cannot perform.
 *
 * The deeper reason is the product's, not the transport's. **A vendor does not become watched by
 * being added to a list.** It becomes watched when this codebase calls it and an index pass finds
 * the call site. Registering a vendor and watching a vendor are two facts about two different
 * things — Sync's configuration, and the customer's code — and a button that collapsed them would
 * be the one claim `web/CLAUDE.md` refuses most: rendering one nothing as another.
 *
 * So the panel answers the question the button asks by splitting it in two:
 *
 * - **Registered here and not watched.** These are already in the registry. They are missing from
 *   the table behind this drawer for one reason, and the reason is not a failure — no call site in
 *   this repository binds to them yet. Each opens on what it would take: the SDK package an index
 *   pass looks for, and the command that runs the pass.
 * - **Not registered at all.** That is an edit to `generated-vendors.yaml` and, in its own
 *   header's words, *"this file and nothing else"*. The exact block is here, copyable, with every
 *   field named — because what the console can honestly offer is the invocation, never a button
 *   that would have to lie about what it did.
 *
 * ## Which nothing it is, three times over
 *
 * The list is meaningless without the state of the index pass, and that is `useOverview`'s
 * `last_index_run`: a repository that has **never been indexed** lists every registered vendor
 * here for that reason alone, which is not the same answer as a completed pass that looked and
 * found no call site. A pass still in flight is a third. The sentence above the list switches on
 * all three rather than letting a reader assume the second.
 *
 * ## Why the catalogue and not the adapter inventory
 *
 * `/api/adapters` is deployment-wide and holds no notion of *watched here*, so classifying against
 * it would mean re-deriving a state the API already computes — and the KPI strip directly above
 * this drawer's trigger already renders that computed state. Two derivations of one fact is the
 * drift `CLAUDE.md` calls the most expensive kind. `fetchCatalogue` is read on the query key
 * `IntegrationsKpis` already uses, so the tiles and this list cannot disagree and no second
 * request is issued.
 */

import { useQuery } from "@tanstack/react-query"
import { Boxes, FileCode2, Plus } from "lucide-react"
import { useState, type ComponentType, type ReactNode, type SVGProps } from "react"

import { useOverview } from "@/api/queries"
import { FactList, type Fact } from "@/components/fact-list"
import { InfoHint } from "@/components/info-hint"
import { RelativeTime } from "@/components/relative-time"
import { Skeleton } from "@/components/skeleton"
import { ErrorState, LoadingState } from "@/components/states"
import { Absent } from "@/components/status"
import { AdapterTierTag, Tag } from "@/components/tag"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { Button } from "@/components/ui/button"
import { CODED_SOURCE_NOTE } from "@/features/vendors/vendor-card"
import { VendorMark } from "@/features/vendors/vendor-mark"
import { type Catalogue, type CatalogueRow, fetchCatalogue } from "@/features/vendors/catalogue"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetSection,
  SheetTitle,
  SheetTrigger,
} from "@/vendor/supabase/ui/sheet"

/**
 * The two states a vendor can be in here, and what each one actually says.
 *
 * The words are the ones `features/settings/integrations-catalogue-panel.tsx` prints for the same
 * payload, deliberately — a second spelling of one vocabulary is two screens disagreeing about
 * what "staged" means. `watched` is absent because a watched vendor is in the table rather than in
 * this drawer.
 */
export const UNWATCHED_STATE_MEANING: Record<string, string> = {
  staged:
    "A specification for this vendor is cached on disk, so a scan could bind a call site today. It says nothing about whether this codebase calls it.",
  available:
    "Registered, and neither a specification nor a call site has arrived. The ordinary state of an integration this codebase does not use.",
}

/**
 * The block to paste, with every field the registry reads named on its own line.
 *
 * Copied from `generated-vendors.yaml`'s own header rather than paraphrased, because that header
 * is the thing `_generated_vendors` actually enforces: exactly one of `manifest` and `spec`, and
 * a language binding that has spoken completely. The example is a placeholder vendor on purpose —
 * every real row in that file was confirmed by fetching its path, and a plausible-looking real
 * name here would be an unverified row wearing the costume of a verified one.
 */
export const VENDOR_YAML_TEMPLATE = `# Append to generated-vendors.yaml. A row names exactly one of \`manifest\` and \`spec\`.
- vendor_id: acme                  # what \`--vendor\` selects, and what every row this vendor produces is keyed by
  repo: acme/acme-sdk-python       # owner/name of the repository the generated SDK lives in
  manifest: .stats.yml             # Stainless. \`.speakeasy/workflow.yaml\` for Speakeasy.
# spec: api/openapi.yml            # instead of \`manifest\`, where the vendor commits the document itself
# sdk_spec: api/openapi.sdk.yml    # optional: a second document naming the SDK method per operation
# symbols: acme-openapi            # optional: which specification-reading rule builds the symbol map
  sdk_bindings:                    # what a customer imports to reach this vendor, per language
    typescript:
      package: "@acme/sdk"         # the npm name, which is also the import specifier
      symbol_root: acme            # defaults to \`package\`; declare it only where they differ
    python:
      distribution: acme           # what pip installs
      module: acme                 # what source imports
# noise_kinds: []                  # optional: oasdiff rule ids this vendor emits in volume without meaning`

/**
 * The banded pane header, without the scroll mechanic.
 *
 * Not `components/pane.tsx`: `PanelPane` composes `Pane`/`PaneScroll`, which is a second scroll
 * region inside a drawer that already scrolls — and its own docstring is explicit that exactly one
 * `PaneScroll` belongs to a pane, because a reader cannot tell which of two scrollbars they are
 * holding. This is the same chrome at the same measurements with the body left to flow.
 */
function Banded({
  label,
  icon: Icon,
  actions,
  children,
}: {
  label: string
  icon: ComponentType<SVGProps<SVGSVGElement>>
  actions?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="flex min-w-0 flex-col rounded-surface border border-line bg-card">
      <header className="flex h-row-lg shrink-0 items-center gap-row border-b border-line bg-secondary px-row">
        <Icon aria-hidden="true" className="size-4 shrink-0 text-graphics" />
        <h3 className="min-w-0 truncate text-section">{label}</h3>
        {actions !== undefined && (
          <span className="ml-auto flex shrink-0 items-center gap-field">{actions}</span>
        )}
      </header>
      <div className="flex min-w-0 flex-col gap-section p-section">{children}</div>
    </section>
  )
}

/**
 * The copy affordance, with its own failure said out loud.
 *
 * A clipboard write can be refused by the browser and a button that silently did nothing would
 * leave a reader believing they hold text they do not. The block above stays selectable either
 * way, which is what the failure branch points at.
 */
function CopyBlock({ text, label }: { text: string; label: string }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle")
  return (
    <div className="flex flex-col gap-field">
      <pre className="overflow-x-auto rounded-control border border-line bg-surface-subtle px-field py-field font-mono text-meta leading-relaxed text-ink select-all">
        {text}
      </pre>
      <div className="flex flex-wrap items-center gap-row">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => {
            void navigator.clipboard.writeText(text).then(
              () => setState("copied"),
              () => setState("failed"),
            )
          }}
        >
          {state === "copied" ? "Copied" : label}
        </Button>
        {state === "failed" && (
          <span className="text-meta text-ink-muted">
            The browser refused the clipboard. Select the block above instead — it is the whole
            text.
          </span>
        )}
      </div>
    </div>
  )
}

/** `typescript: @acme/sdk · python: acme`, or nothing where the row declares no binding. */
function bindingNames(row: CatalogueRow): string[] {
  return Object.entries(row.sdk_bindings).map(([language, binding]) => {
    const name = binding.package ?? binding.distribution ?? binding.module
    return `${language}: ${name ?? "—"}`
  })
}

/**
 * Where this vendor's specification comes from.
 *
 * A coded adapter with no source is not a missing value — it is written in this repository, which
 * is the fact `vendor-card.tsx` already names, imported rather than respelled.
 */
function servedFrom(row: CatalogueRow): ReactNode {
  if (row.source !== null) return <span className="font-mono text-meta break-words">{row.source}</span>
  if (row.tier === "coded") return CODED_SOURCE_NOTE
  return <Absent>no source recorded against this adapter</Absent>
}

function rowFacts(row: CatalogueRow): Fact[] {
  const names = bindingNames(row)
  return [
    { label: "Adapter tier", value: <AdapterTierTag tier={row.tier} /> },
    { label: "Served from", value: servedFrom(row) },
    {
      label: "Specification cached",
      value:
        row.staged === null ? (
          <Absent>nothing has fetched one for this vendor</Absent>
        ) : (
          <span className="font-mono text-meta">
            {row.staged.tag ?? "cached, no tag recorded"}
            {row.staged.symbols === null ? " · no symbol map built" : ` · ${row.staged.symbols} symbols`}
          </span>
        ),
    },
    {
      // The one row-specific answer to "what would make this watched", and it is concrete: an
      // index pass looks for these package names in this repository's source.
      label: "Imports an index pass looks for",
      value:
        names.length === 0 ? (
          <Absent>no SDK binding declared, so a pass has no package name to match</Absent>
        ) : (
          <span className="font-mono text-meta break-words">{names.join(" · ")}</span>
        ),
    },
    {
      label: "Vendor changes recorded",
      value:
        row.changes_recorded === 0 ? (
          <Absent>none recorded</Absent>
        ) : (
          <span className="font-mono tabular-nums">{row.changes_recorded.toLocaleString()}</span>
        ),
    },
  ]
}

/**
 * Whether a pass has ever looked, which is what makes the list below mean anything.
 *
 * Three answers and they are three different facts: never indexed, a pass in flight, a pass that
 * finished. Collapsing the first onto the third would tell a reader that Sync looked at their code
 * and found nothing, when nothing has looked at all.
 */
function IndexPassNote({ repoId }: { repoId: string }) {
  const overview = useOverview(repoId)

  if (overview.isPending) return <Skeleton width="18rem" />
  if (overview.isError) {
    return (
      <p className="max-w-prose text-body text-ink-muted">
        <Absent>the overview did not answer</Absent>, so nothing here can say whether an index pass
        has ever run over this repository — and without that, this list cannot tell you which
        nothing it is.
      </p>
    )
  }

  const pass = overview.data.last_index_run
  if (pass === null) {
    return (
      <p className="max-w-prose text-body text-ink-muted">
        <span className="text-ink">This repository has never been indexed.</span> Every registered
        vendor is listed below for that reason alone — nothing has looked for a call site yet, which
        is not the same answer as looking and finding none.
      </p>
    )
  }
  if (pass.finished_at === null) {
    return (
      <p className="max-w-prose text-body text-ink-muted">
        <span className="text-ink">An index pass started and has not finished.</span> This list is
        what the last completed pass bound; a pass that is still running may move it.
      </p>
    )
  }
  return (
    <p className="max-w-prose text-body text-ink-muted">
      The last index pass finished <RelativeTime iso={pass.finished_at} />. These are the registered
      vendors it bound no call site to in this repository — a measured answer about this codebase,
      not an absence of one. Staleness, never liveness: nothing here says a pass is running now.
    </p>
  )
}

/** One registered, unwatched vendor: the header a reader scans, and the detail behind it. */
function UnwatchedVendor({ row }: { row: CatalogueRow }) {
  return (
    <AccordionItem value={row.vendor_id} className="border-line">
      <AccordionTrigger className="gap-row px-field">
        <span className="flex min-w-0 items-center gap-row">
          <VendorMark vendorId={row.vendor_id} />
          <span className="min-w-0 truncate font-mono text-body text-ink">{row.vendor_id}</span>
          <Tag title={UNWATCHED_STATE_MEANING[row.state]}>{row.state}</Tag>
        </span>
      </AccordionTrigger>
      <AccordionContent className="px-field">
        <FactList facts={rowFacts(row)} />
      </AccordionContent>
    </AccordionItem>
  )
}

/** The registered set, minus what this repository already calls. */
function RegisteredNotWatched({ repoId, catalogue }: { repoId: string; catalogue: Catalogue }) {
  // The same scope discipline the page itself applies: the catalogue echoes the repository it was
  // computed for, and `state` is only a fact about *this* repository when the two agree. Rendering
  // another scope's classification here would be the `codebases-panel.tsx` defect again.
  if (catalogue.repo_id !== repoId) {
    return (
      <p className="max-w-prose text-body text-ink-muted">
        The catalogue that arrived names its scope as{" "}
        <span className="font-mono">{catalogue.repo_id ?? "the whole fleet"}</span>, not{" "}
        <span className="font-mono">{repoId}</span>. Whether a vendor is watched is a fact about one
        repository, so no vendor is classified here rather than classified against the wrong one.
      </p>
    )
  }

  const unwatched = catalogue.integrations
    .filter((row) => row.state !== "watched")
    .sort((a, b) => a.vendor_id.localeCompare(b.vendor_id))

  if (unwatched.length === 0) {
    return (
      <p className="max-w-prose text-body text-ink-muted">
        Every one of the {catalogue.total.toLocaleString()} registered vendors is watched in this
        repository, so the table behind this drawer is the whole registry. Adding one means
        registering a new vendor — the block below.
      </p>
    )
  }

  return (
    <>
      <IndexPassNote repoId={repoId} />
      <Accordion type="single" collapsible className="rounded-control border border-line">
        {unwatched.map((row) => (
          <UnwatchedVendor key={row.vendor_id} row={row} />
        ))}
      </Accordion>
      <div className="flex flex-col gap-field">
        <p className="max-w-prose text-body text-ink-muted">
          Import the package a row names, then run a pass. The console cannot run one — no route it
          can call writes to the graph or starts work — so this is the invocation rather than a
          button.
        </p>
        <code className="block overflow-x-auto rounded-control border border-line bg-surface-subtle px-field py-field font-mono text-meta text-ink select-all">
          uv run sync index --repo {repoId}
        </code>
      </div>
    </>
  )
}

/** The catalogue read, with each of its four answers kept apart. */
function RegisteredSection({ repoId }: { repoId: string }) {
  const query = useQuery({
    // `IntegrationsKpis` on this same screen already holds this key, so the tiles above the trigger
    // and the list inside the drawer are one read and cannot contradict each other.
    queryKey: ["integrations-catalogue", repoId],
    queryFn: ({ signal }) => fetchCatalogue(repoId, signal),
  })

  // A count only where the catalogue answered: a header reading "0 of 0" while the read is in
  // flight is a claim about the registry that nothing has measured yet.
  const tally = query.isSuccess
    ? {
        unwatched: query.data.integrations.filter((row) => row.state !== "watched").length,
        total: query.data.total,
      }
    : null

  return (
    <Banded
      label="Registered here, not watched"
      icon={Boxes}
      actions={
        tally === null ? null : (
          <span className="font-mono text-meta text-ink-muted tabular-nums">
            {tally.unwatched.toLocaleString()} of {tally.total.toLocaleString()}
          </span>
        )
      }
    >
      <p className="max-w-prose text-body text-ink-muted">
        These vendors are already registered in this deployment. None of them is in the table
        behind this drawer, and nothing has failed:{" "}
        <span className="text-ink">
          a registered vendor appears there once an index pass finds a call site in this repository
          binding to it.
        </span>{" "}
        Being watched is a fact about your code, not a switch in this console.
      </p>

      {query.isPending ? (
        <LoadingState what="the integrations catalogue" />
      ) : query.isError ? (
        <ErrorState
          error={query.error}
          what="the integrations catalogue"
          onRetry={() => void query.refetch()}
        />
      ) : (
        <RegisteredNotWatched repoId={repoId} catalogue={query.data} />
      )}
    </Banded>
  )
}

/** The other addition: a vendor the registry has never heard of. */
function UnregisteredSection() {
  return (
    <Banded label="Not registered in this deployment" icon={FileCode2}>
      <p className="max-w-prose text-body text-ink-muted">
        A vendor missing from the list above is not registered at all. Registering one is an edit to{" "}
        <span className="font-mono">generated-vendors.yaml</span> and, in that file's own words,{" "}
        <span className="text-ink">this file and nothing else</span>. Sync reaches a vendor by
        reading the specification its SDK is generated from, so a row carries where that document
        lives and which package a customer imports — never knowledge about the vendor's API.
      </p>

      <CopyBlock text={VENDOR_YAML_TEMPLATE} label="Copy the YAML block" />

      <p className="max-w-prose text-meta text-ink-muted leading-relaxed">
        Every row already in that file was confirmed by fetching its path before it was committed,
        and the responses are held under <span className="font-mono">tests/fixtures/manifests/</span>
        . A row pointing at a repository that does not exist still registers, is still offered on
        the command line, and fails on the first scan — a runtime failure wearing the costume of
        support. This deployment may also be reading a different file:{" "}
        <span className="font-mono">SYNC_GENERATED_VENDORS</span> overrides the path.
      </p>

      <p className="max-w-prose text-meta text-ink-muted leading-relaxed">
        Restart the API and the vendor joins the list above. It joins the table behind this drawer
        only once an index pass finds a call site binding this repository to it.
      </p>
    </Banded>
  )
}

/**
 * The trigger and the panel, in one component so a screen adds the affordance in one line.
 *
 * A drawer rather than a modal dialog: the panel is two long sections over a card grid, and a
 * centred box would either crop them or cover the grid it is explaining. `CLAUDE.md`'s chassis
 * ruling puts detail in a drawer for the same reason.
 */
export function AddVendorDrawer({ repoId }: { repoId: string }) {
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button type="button" variant="outline" size="sm">
          <Plus aria-hidden="true" data-icon="inline-start" />
          Add a vendor
        </Button>
      </SheetTrigger>
      <SheetContent side="right" size="lg" className="flex flex-col overflow-y-auto">
        <SheetHeader>
          <div className="flex items-center gap-row">
            <SheetTitle className="text-emphasis">Add a vendor</SheetTitle>
            <InfoHint label="About adding a vendor">
              Two different additions wear one word. Registering a vendor tells Sync a
              specification exists and where; watching one is the index finding a call site in your
              code. The first is a configuration edit, the second is a fact about your codebase, and
              neither is something this console performs — it reads the graph and never writes to
              it.
            </InfoHint>
          </div>
          <SheetDescription>
            Nothing here adds anything. The console reads the graph and no route it can call writes
            to it, so this panel says which of the two additions you need and hands you the exact
            text for it.
          </SheetDescription>
        </SheetHeader>
        <SheetSection className="flex flex-col gap-section">
          <RegisteredSection repoId={repoId} />
          <UnregisteredSection />
          <p className="max-w-prose text-meta text-ink-muted leading-relaxed">
            Closing this drawer changes nothing, because opening it changed nothing. Every route
            this console holds is a read.
          </p>
        </SheetSection>
      </SheetContent>
    </Sheet>
  )
}
