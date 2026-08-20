/**
 * Every page this workspace has, grouped under the pipeline stage it answers, and the settings
 * that have to be in place before any stage runs at all.
 *
 * The Overview used to carry four tables that each belonged to another screen — open findings,
 * index coverage, change units, observed telemetry — and a reader who wanted any of them scrolled
 * past a truncated copy to reach the real one. This is what replaced them: the doors, with the
 * question each page answers, taken from `lib/routes.ts` so a page cannot appear here under a
 * sentence that has drifted from the one the header and the palette render.
 */

import type { ReactNode } from "react"
import { Link } from "react-router"

import { STAGE_DOES, pagesByStage } from "@/features/repositories/stage-pages"
import { LOOP_PREREQUISITES, SETTING_GROUPS } from "@/features/settings/groups"
import { destinationHref } from "@/lib/routes"


function GridCard({ title, does, children }: { title: string; does: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-section rounded-surface border border-line bg-card p-section">
      <div className="flex flex-col gap-field">
        <h3 className="text-emphasis">{title}</h3>
        <p className="text-meta leading-snug text-ink-muted">{does}</p>
      </div>
      <ul className="flex flex-col gap-field">{children}</ul>
    </div>
  )
}

function DoorRow({ to, label, question }: { to: string; label: string; question: string }) {
  return (
    <li>
      <Link
        to={to}
        className="flex flex-col gap-field rounded-control px-row py-row transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      >
        <span className="text-body text-ink">{label}</span>
        <span className="text-meta leading-snug text-ink-muted">{question}</span>
      </Link>
    </li>
  )
}

export function WorkflowGrid({ repoId }: { repoId: string }) {
  return (
    <section aria-label="Where each stage is answered" className="flex flex-col gap-section">
      <h2 className="furniture text-meta text-ink-muted">Where each stage is answered</h2>

      <div className="grid gap-section sm:grid-cols-2 xl:grid-cols-3">
        {pagesByStage().map(({ stage, pages }) => (
          <GridCard key={stage} title={stage} does={STAGE_DOES[stage]}>
            {pages.map((route) => {
              const href = destinationHref(route, { repoId })
              if (href === null) return null
              return (
                <DoorRow key={route.path} to={href} label={route.label} question={route.question} />
              )
            })}
          </GridCard>
        ))}

        {/* Settings is not a stage — it configures the system the stages run in, which is why
            `lib/routes.ts` files it as a destination rather than a level. It sits in the grid
            anyway because a deployment with no model connected writes no patch, and the five
            stages above give a reader no way to find that out. */}
        <GridCard
          title="Settings"
          does="what the loop needs before any stage above can run end to end"
        >
          {LOOP_PREREQUISITES.map(({ id, why }) => {
            const group = SETTING_GROUPS.find((entry) => entry.id === id)
            if (group === undefined) return null
            return (
              <DoorRow key={id} to={`/settings?group=${id}`} label={group.label} question={why} />
            )
          })}
        </GridCard>
      </div>
    </section>
  )
}
