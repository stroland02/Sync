/**
 * Signals: one panel per attached integration, grouped by role, for one repository.
 *
 * `docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md:435` places this
 * level under API Services, and `:455-459` (section *M5 — The integration layer*) defines the
 * three roles. Both the role names and their relationship sentences live in `roles.ts` rather
 * than in this file, because the header below states which roles have an integration attached
 * and which do not, and a header that restated the roster would be the same fact in two places.
 *
 * **A panel per role is not a promise that every role has one.** This deployment has two: the
 * static index gives the vendor role a real answer (which vendors this repository's code calls),
 * and `observed_call` / `observed_shape` / `observed_error_window` give the signal-source role a
 * real answer (what traffic showed up, and how it behaved). Nothing in this tree gives the
 * human-surface role an answer at all — no adapter, no configuration table, no row anywhere
 * names a Slack channel, a Linear issue, a Notion page, or a GitHub pull request as a configured
 * destination. Sync *does* open pull requests, at the Solution Workflow's own Pull Request level
 * (`:442`) — but that is the product delivering its remediation output through a hardcoded
 * mechanism, not a human-surface integration this graph tracks the way it tracks a vendor or a
 * signal source. There is nothing to query, which is why that panel is not an empty table: an
 * empty table would claim a question was asked.
 *
 * Grouped by role because the graph attaches at three different points, not because three
 * columns read as balanced. A vendor's call site, a signal source's traffic row and a
 * human-surface delivery would each join the graph differently if the third one existed, and
 * showing them as one undifferentiated "integrations" list would erase the distinction the data
 * actually carries.
 *
 * B94 records what is still missing and why it is blocked rather than merely undone: the level
 * is complete as an honest account of this deployment, and incomplete as the specification's
 * Signals level, until M5 attaches a human surface and gives the correlation join something to
 * render across all three.
 */

import { useParams } from "react-router"
import type { ReactNode } from "react"

import { IndexCoverageCard } from "@/features/repositories/index-coverage-card"
import { SignalSourcePanel } from "@/features/telemetry/signal-source-panel"
import { NotAttachedState } from "@/features/signals/not-attached-state"
import {
  ATTACHED_ROLES,
  HUMAN_SURFACE_ROLE,
  SIGNAL_SOURCE_ROLE,
  UNATTACHED_ROLES,
  VENDOR_ROLE,
  type SignalRole,
} from "@/features/signals/roles"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { UnknownRoute } from "@/layouts/unknown-route"

function names(roles: readonly SignalRole[]): string {
  return roles.map((entry) => entry.role).join(", ")
}

function RoleSection({ role, children }: { role: SignalRole; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-section">
      <div className="flex flex-col gap-field">
        <h2 className="text-section">{role.role}</h2>
        <p className="max-w-prose text-body text-muted-foreground">{role.relationship}</p>
      </div>
      {children}
    </div>
  )
}

export function SignalsPage() {
  const { repoId } = useParams<{ repoId: string }>()
  if (repoId === undefined) return <UnknownRoute />
  return <SignalsDetail repoId={repoId} />
}

function SignalsDetail({ repoId }: { repoId: string }) {
  return (
    <section className="flex flex-col gap-8">
      <Breadcrumbs
        trail={[
          { label: "Fleet", to: "/" },
          { label: repoId, to: `/repositories/${encodeURIComponent(repoId)}` },
          { label: "Signals" },
        ]}
      />
      <div className="flex flex-col gap-section">
        <h1 className="font-mono text-page">{repoId}</h1>
        <p className="max-w-prose text-body text-muted-foreground">
          Every integration attached to this repository's graph, grouped by the role it plays. One
          panel per role below, and a panel is not evidence that an integration stands behind it.
        </p>
        <p className="max-w-prose text-body text-muted-foreground">
          Roles with an integration attached to this deployment: {names(ATTACHED_ROLES)}. What
          each of those has to say about this repository is its own panel's answer, and a panel
          with no rows in it is a quiet integration rather than a missing one.
          {UNATTACHED_ROLES.length > 0 && (
            <>
              {" "}
              Roles with none: {names(UNATTACHED_ROLES)}. A role with nothing attached was never
              asked, because there is no adapter, no configuration table and no row here to ask —
              which is a different fact from an attached integration that was asked and had
              nothing to report.
            </>
          )}
        </p>
      </div>

      <RoleSection role={VENDOR_ROLE}>
        <IndexCoverageCard repoId={repoId} />
      </RoleSection>

      <RoleSection role={SIGNAL_SOURCE_ROLE}>
        <SignalSourcePanel repoId={repoId} />
      </RoleSection>

      <RoleSection role={HUMAN_SURFACE_ROLE}>
        <NotAttachedState detail={HUMAN_SURFACE_ROLE.absence} />
      </RoleSection>
    </section>
  )
}
