/**
 * The Overview: which repository to open, and the four fleet counts while you decide.
 *
 * **One question per screen.** This level asks which repository, and everything that answered a
 * different question has moved to where that question is asked. The fleet-wide change-unit table
 * and the vendor distribution went to the Codebase screen, where they are scoped to one repository
 * and therefore actionable; a fleet-wide table on a screen whose job is choosing between
 * repositories made the choosing harder rather than easier.
 *
 * **The name.** This destination was titled "Repositories", labelled "Codebases" in the route
 * registry, and sits at the `Fleet` level — three names for one screen. It is "Overview" now in
 * everything a reader sees. The *level* keeps the specification's word, because
 * `docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md` is what
 * `tests/test_console_hierarchy.py` checks `GRAPH_LEVELS` against, and a display rename is not a
 * hierarchy change.
 *
 * **No page-level action.** `PageHeader`'s `actions` slot carried "Review proposed patch", pointing
 * at whichever run happened to be the newest with an opened pull request. With nine change units
 * open that reads as *the* patch, which is a claim about priority the data does not make. The
 * action belongs on the change-unit row it acts on, beside that row's own standing and checkpoint
 * age, where it also reads as the log of what happened to that change.
 *
 * **The repository list is rows, not cards.** Five cards spent a tile each on one repository's name
 * while answering one question; rows answer it in a line and let a reader compare down a column.
 * `codebases-panel.tsx` keeps the scoped-answer discipline unchanged — `/api/overview` echoes the
 * scope it was computed for, one query per repository, and `openFindings` stays null rather than
 * zero until that repository's own answer arrives.
 *
 * **What stays, and why it is not clutter.** The four counts, the standing limits, the
 * composite-health refusal and the three footnotes are the qualifications that make every figure on
 * this screen readable. `CLAUDE.md` protects four distinctions and the console architecture plan's
 * *Establish 2* reproduces twenty-four sentences that may be restyled and re-placed but never
 * shortened; the absence footnote in particular points at "the repository list below", which is why
 * that list stays on this screen rather than moving into the sidebar.
 */

import { useState } from "react"

import { Button } from "@/components/ui/button"
import { FactTile } from "@/components/fact-tile"
import { CodebasesPanel, type CodebaseFilter } from "@/features/fleet/codebases-panel"
import { FleetFacts } from "@/features/fleet/fleet-facts"
import { ScreenLimitsCard } from "@/features/fleet/screen-limits"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { ControlBar } from "@/layouts/control-bar"
import { PageHeader } from "@/layouts/page-header"
import { chipSurface } from "@/lib/selectable-surface"

const DEFAULT_QUESTION =
  "All code repositories monitored by Sync, their attached API vendors, and active migrations."

const FILTERS: [CodebaseFilter, string][] = [
  ["ALL", "All repositories"],
  ["NEEDS_REVIEW", "With active remediations"],
  ["CLEAN", "Clean repositories"],
]

export interface FleetPageProps {
  readonly question?: string
}

export function FleetPage({ question = DEFAULT_QUESTION }: FleetPageProps) {
  const [filter, setFilter] = useState<CodebaseFilter>("ALL")

  return (
    <section className="flex flex-col gap-section">
      {/* "Overview", once. This destination was titled "Repositories", labelled "Codebases" in the
          route registry and sits at the "Fleet" level — three names for one screen, which is its own
          kind of clutter. The *level* keeps the specification's word; only what a reader sees
          changes, so `tests/test_console_hierarchy.py` is untouched.

          No page-level action. "Review proposed patch" pointed at whichever run happened to be the
          newest with an opened pull request, which reads as *the* patch when there are nine change
          units. It belongs on the change-unit row it acts on, beside that row's own standing. */}
      <PageHeader
        title="Overview"
        question={question}
        trail={<Breadcrumbs trail={[{ label: "Overview" }]} />}
      />

      {/* Filter Tabs & Scope Description */}
      <ControlBar>
        <div className="flex flex-wrap items-center gap-row">
          {FILTERS.map(([value, label]) => (
            <Button
              key={value}
              type="button"
              size="sm"
              variant="outline"
              aria-pressed={filter === value}
              className={chipSurface(filter === value)}
              onClick={() => setFilter(value)}
            >
              {label}
            </Button>
          ))}
        </div>
        <span className="text-meta text-muted-foreground">
          Repositories monitored across the organization
        </span>
      </ControlBar>

      {/* 4-card metric strip */}
      <FleetFacts />

      {/* The repository list is the screen. This level's one question is which repository to open,
          and everything that answered a different question has moved to where that question is
          asked: the fleet-wide change-unit table to the Codebase screen, where it is scoped to one
          repository and therefore actionable, and the vendor distribution with it. */}
      <CodebasesPanel filter={filter} />

      <div className="grid gap-section xl:grid-cols-2">
        <div className="flex min-w-0 flex-col gap-section">
          <FactTile
            label="Health score policy"
            value={
              <>
                There is no composite health figure here on purpose. A scalar that averaged three
                gates would collapse "we could not check" onto the same axis as "we checked and it
                passed", which is the failure this console exists to replace. Every figure on this
                screen instead names its own scope, and the panel beside them names what none of
                these figures can tell you at all.
              </>
            }
          />
          <ScreenLimitsCard />
        </div>
      </div>

      {/* Footnotes holding honesty requirements */}
      <div className="flex flex-col gap-row text-meta text-muted-foreground max-w-5xl leading-relaxed pt-section border-t border-border">
        <p>
          A checkpoint age is staleness, not liveness — it says how old the evidence is not whether the run is still going. A change unit collapses findings sharing a vendor change against one repository set; the call-site grain is intact underneath and reachable from every row.
        </p>
        <p>
          A repository the index never indexed has no row — absence is not zero: a repository configured but never indexed has no row in the repository list below, and the same absence as a repository nobody ever configured.
        </p>
        <p>
          A finding retried three times writes three attempts here and counts once toward the corpus grain.
        </p>
      </div>
    </section>
  )
}
