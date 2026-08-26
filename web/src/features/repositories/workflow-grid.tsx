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

import { PanelPane } from "@/components/pane"
import { STAGE_DOES, pagesByStage } from "@/lib/stage-pages"
import { LOOP_PREREQUISITES, SETTING_GROUPS } from "@/features/settings/groups"
import { destinationHref } from "@/lib/stage-pages"

function GridCard({ title, does, children }: { title: string; does: string; children: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-row rounded-surface border border-line bg-surface p-section">
      <div className="flex flex-col gap-field">
        <h3 className="text-emphasis">{title}</h3>
        <p className="text-meta leading-snug text-ink-muted">{does}</p>
      </div>
      <ul className="flex flex-col gap-field">{children}</ul>
    </div>
  )
}

function DoorRow({ to, label, detail, title }: { to: string; label: string; detail?: string; title?: string }) {
  return (
    <li>
      <Link
        to={to}
        title={title}
        className="flex flex-col gap-field rounded-control px-row py-field transition-colors hover:bg-surface-subtle focus:outline-none focus:ring-1 focus:ring-ring"
      >
        <span className="text-body text-ink">{label}</span>
        {/* Optional since `CI-W597`. The stage doors carried `RouteEntry.question` and no longer
            do; the settings prerequisites below carry their own `why`, which is a local
            explanation rather than a sentence the registry held. */}
        {detail ? (
          <span className="text-meta leading-snug text-ink-muted">{detail}</span>
        ) : null}
      </Link>
    </li>
  )
}

export function WorkflowGrid({ repoId, span }: { repoId: string; span?: string }) {
  return (
    <PanelPane className={span} label="Where each stage is answered" bodyClassName="p-section">
      {/* auto-fill rather than a fixed column count: this pane is eight of twelve columns on a
          wide window and the full width when the bento stacks, and a fixed count would leave a
          widow at one of the two. */}
      <div className="grid gap-section grid-cols-[repeat(auto-fill,minmax(240px,1fr))]">
        {pagesByStage().map(({ stage, pages }) => {
          const doors = pages
            .map((route) => ({ route, href: destinationHref(route, { repoId }) }))
            .filter((door): door is { route: (typeof pages)[number]; href: string } => door.href !== null)
          return (
            <GridCard key={stage} title={stage} does={STAGE_DOES[stage]}>
              {doors.length === 0 ? (
                /* A fact about the route registry, not about the graph: nothing here says this
                   stage produced nothing, only that no page in this workspace opens onto it. */
                <li className="text-meta text-ink-muted">
                  no page in this workspace answers this stage yet
                </li>
              ) : (
                doors.map(({ route, href }) => (
                  <DoorRow key={route.path} to={href} label={route.label} />
                ))
              )}
            </GridCard>
          )
        })}

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
            // Label only -- the owner ruled the descriptions out on 2026-08-25; the sentence
            // survives as the row's tooltip.
            return <DoorRow key={id} to="/settings" label={group.label} title={why} />
          })}
        </GridCard>
      </div>
    </PanelPane>
  )
}
