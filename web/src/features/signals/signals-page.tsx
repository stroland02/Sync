/**
 * Signals: one panel per attached integration, grouped by role, for one repository.
 *
 * `docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md:435` places this
 * level under API Services, and `:455-459` (section *M5 — The integration layer*) is the
 * authority for the three roles below and their relationship to the graph — restated here
 * rather than invented, because the table already says it better than a paraphrase would:
 *
 *   Vendor         — a subject: code calls it, and it can break you.
 *   Signal source  — feeds the graph: reports that something broke, deployed, or changed.
 *   Human surface  — consumes: where a finding is delivered and a person answers.
 *
 * **A panel per role is not a promise that every role has one.** This deployment has two: the
 * static index gives the vendor role a real answer (which vendors this repository's code
 * calls), and `observed_call` / `observed_shape` / `observed_error_window` give the
 * signal-source role a real answer (what traffic showed up, and how it behaved). Nothing in
 * this tree gives the human-surface role an answer at all — no adapter, no configuration
 * table, no row anywhere names a Slack channel, a Linear issue, a Notion page, or a GitHub
 * pull request as a configured destination. Sync *does* open pull requests, at the Solution
 * Workflow's own Pull Request level (`:442`) — but that is the product delivering its
 * remediation output through a hardcoded mechanism, not a human-surface integration this graph
 * tracks the way it tracks a vendor or a signal source. There is nothing to query, which is why
 * that panel below is not an empty table: an empty table would claim a question was asked.
 *
 * Grouped by role because the graph attaches at three different points, not because three
 * columns read as balanced. A vendor's call site, a signal source's traffic row and a
 * human-surface delivery would each join the graph differently if the third one existed, and
 * showing them as one undifferentiated "integrations" list would erase the distinction the
 * data actually carries.
 */

import { useParams } from "react-router"
import type { ReactNode } from "react"

import { IndexCoverageCard } from "@/features/repositories/index-coverage-card"
import { SignalSourcePanel } from "@/features/telemetry/signal-source-panel"
import { NotAttachedState } from "@/features/signals/not-attached-state"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { UnknownRoute } from "@/layouts/unknown-route"

function RoleSection({
  role,
  relationship,
  children,
}: {
  role: string
  relationship: string
  children: ReactNode
}) {
  return (
    <div className="flex flex-col gap-section">
      <div className="flex flex-col gap-field">
        <h2 className="text-section">{role}</h2>
        <p className="max-w-prose text-body text-muted-foreground">{relationship}</p>
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
          Every integration attached to this repository's graph, grouped by the role it plays:
          a vendor is a subject this code calls, a signal source feeds the graph by reporting
          that something broke or changed, and a human surface is where a finding would be
          delivered. Not every role has a panel below with rows in it — the section itself says
          which do.
        </p>
      </div>

      <RoleSection role="Vendor" relationship="A subject: code in this repository calls it, and it can break you.">
        <IndexCoverageCard repoId={repoId} />
      </RoleSection>

      <RoleSection
        role="Signal source"
        relationship="Feeds the graph: reports that something broke, deployed, or changed."
      >
        <SignalSourcePanel repoId={repoId} />
      </RoleSection>

      <RoleSection
        role="Human surface"
        relationship="Consumes: where a finding is delivered and a person answers."
      >
        <NotAttachedState
          detail={
            "No adapter, no configuration table and no row anywhere in this deployment names " +
            "a delivery destination — not a Slack channel, a Linear issue, a Notion page, or " +
            "a configured GitHub surface. This is different from an attached integration that " +
            "is quiet: a quiet integration was asked and had nothing to report, and this one " +
            "was never asked, because nothing exists here to ask."
          }
        />
      </RoleSection>
    </section>
  )
}
