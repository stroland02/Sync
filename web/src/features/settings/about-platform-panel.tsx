/**
 * About / How This Works panel — platform documentation and architectural explanations in Settings.
 *
 * Implements the owner ruling from `docs/superpowers/plans/2026-08-18-static-cards-move-to-settings.md`:
 * Static descriptive cards and platform explanations live in Settings so working screens focus purely
 * on live dynamic data and active findings.
 */

import { SettingCard } from "@/features/settings/setting-card"
import { usePanelStatus } from "@/features/settings/panel-status"
import { Badge } from "@/vendor/supabase/ui/badge"

export function AboutPlatformPanel() {
  usePanelStatus([
    {
      kind: "none",
      why: "reference — the platform's own vocabulary, in prose. Nothing here is read from the graph, so nothing here counts or pages.",
    },
  ])

  return (
    <div className="flex flex-col gap-section">
      <div className="flex flex-col gap-field pb-field border-b border-line">
        <h2 className="text-emphasis font-medium text-ink">About Sync & Platform Concepts</h2>
        <p className="text-body text-ink-muted">
          Foundational explanations of Sync&apos;s API Dependency Graph, provenance rungs, adapter tiers,
          abandon reasons, and verification gates.
        </p>
      </div>

      {/* Concept 1: Provenance Rungs */}
      <SettingCard
        title="Provenance Rungs"
        description={
          <div className="flex flex-col gap-row text-body text-ink-muted">
            <p>
              Every binding between customer source code and an external API operation carries the
              provenance rung it was derived from. A finding without an attributed rung is rejected by
              the database schema.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-row pt-row">
              <div className="rounded-surface border border-line bg-surface-muted/30 p-row flex flex-col gap-field">
                <div className="flex items-center gap-row">
                  <Badge>static</Badge>
                  <span className="text-meta font-medium text-ink">AST Call Sites</span>
                </div>
                <p className="text-meta text-ink-muted">
                  Derived directly by static indexing from parsed syntax trees. Represents explicit
                  literal invocations in source code.
                </p>
              </div>

              <div className="rounded-surface border border-line bg-surface-muted/30 p-row flex flex-col gap-field">
                <div className="flex items-center gap-row">
                  <Badge>resolved</Badge>
                  <span className="text-meta font-medium text-ink">Type-Resolved Symbols</span>
                </div>
                <p className="text-meta text-ink-muted">
                  Derived by the TypeScript typechecker following imports and aliases across module
                  boundaries.
                </p>
              </div>

              <div className="rounded-surface border border-line bg-surface-muted/30 p-row flex flex-col gap-field">
                <div className="flex items-center gap-row">
                  <Badge>observed</Badge>
                  <span className="text-meta font-medium text-ink">Runtime Telemetry</span>
                </div>
                <p className="text-meta text-ink-muted">
                  Correlated from runtime OpenTelemetry traces and network spans without executing
                  application logic.
                </p>
              </div>

              <div className="rounded-surface border border-line bg-surface-muted/30 p-row flex flex-col gap-field">
                <div className="flex items-center gap-row">
                  <Badge>unattributed</Badge>
                  <span className="text-meta font-medium text-ink">Vendor Changes</span>
                </div>
                <p className="text-meta text-ink-muted">
                  Raw vendor changes published in upstream changelogs before any detector binds them
                  to a customer call site.
                </p>
              </div>
            </div>
          </div>
        }
      />

      {/* Concept 2: Adapter Tiers */}
      <SettingCard
        title="Adapter Tiers"
        description={
          <div className="flex flex-col gap-row text-body text-ink-muted">
            <p>
              Sync ingests vendor changes through pluggable signal adapters classified into three
              distinct tiers:
            </p>
            <ul className="list-disc list-inside space-y-field text-meta text-ink-muted">
              <li>
                <strong className="text-ink font-mono">coded</strong>: Hand-crafted, first-class
                adapters containing specialized vendor knowledge (e.g. Stripe, OpenAI).
              </li>
              <li>
                <strong className="text-ink font-mono">generated</strong>: Ingested automatically
                from OpenAPI specifications or JSON Schema feeds with semantic diffing.
              </li>
              <li>
                <strong className="text-ink font-mono">mcp</strong>: Bound via Model Context Protocol
                tool definitions for live service interaction.
              </li>
            </ul>
          </div>
        }
      />

      {/* Concept 3: Abandon Reasons & Learning */}
      <SettingCard
        title="Abandoned Runs as Data"
        description={
          <div className="flex flex-col gap-row text-body text-ink-muted">
            <p>
              When an automated remediation run halts because a patch fails verification, breaks
              customer typechecks, or encounters an ambiguous semantic edit, the run is recorded with
              an explicit <code className="font-mono text-ink">abandon_reason</code>.
            </p>
            <p className="text-meta text-ink-muted">
              Abandoned runs are queryable telemetry that teach routing which types of vendor changes
              are mechanically safe for autonomous pull requests and which require human attention.
            </p>
          </div>
        }
      />

      {/* Concept 4: Dual Verification Gates */}
      <SettingCard
        title="Verification Gates"
        description={
          <div className="flex flex-col gap-row text-body text-ink-muted">
            <p>
              Every patch proposed by Sync must pass two mandatory gates before opening a pull
              request:
            </p>
            <ol className="list-decimal list-inside space-y-field text-meta text-ink-muted">
              <li>
                <strong className="text-ink">Static Verification (`tsc`)</strong>: The patched tree
                must compile cleanly with untracked and ignored files held out of the build.
              </li>
              <li>
                <strong className="text-ink">Customer CI</strong>: The customer repository&apos;s own
                automated test suite and lint pipeline must pass on the forge.
              </li>
            </ol>
            <p className="text-meta text-ink-muted mt-field">
              Sync never executes customer application code directly; only their declared compiler
              and toolchain are invoked under isolated environment boundaries.
            </p>
          </div>
        }
      />
    </div>
  )
}
