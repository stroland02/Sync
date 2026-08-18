import { useState } from "react"

import { CodebasesPanel, type CodebaseFilter } from "@/features/fleet/codebases-panel"
import { SettingCard } from "@/features/settings/setting-card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/vendor/supabase/ui/badge"
import { chipSurface } from "@/lib/selectable-surface"

/**
 * Which codebases this workspace holds, and what each one is configured with.
 *
 * The listing arrived here from the Overview, whole. It was ruled off that screen twice — the
 * Overview shows findings for the one workspace already chosen, and a directory of every codebase
 * answers "which workspace am I in", which the scope switcher answers. It is kept rather than
 * deleted because it fixed a real defect: the panel it replaced fetched the fleet-wide overview
 * once and printed that `total_findings` under every card, a false claim about every repository
 * except the one the fleet-wide figure happened to match. `codebases-panel.tsx` carries the
 * scoped-answer discipline that replaced it, and none of it changes by being rendered here.
 *
 * Choosing and configuring a codebase is one question, so the list and the settings that apply to
 * it belong on one screen.
 */

const FILTERS: [CodebaseFilter, string][] = [
  ["ALL", "All repositories"],
  ["NEEDS_REVIEW", "With active remediations"],
  ["CLEAN", "Clean repositories"],
]

export interface CodebasesSettingsPanelProps {
  repoId: string
}

export function CodebasesSettingsPanel({ repoId }: CodebasesSettingsPanelProps) {
  const [filter, setFilter] = useState<CodebaseFilter>("ALL")

  return (
    <div className="flex flex-col gap-section">
      <div className="flex flex-col gap-field pb-field border-b border-line">
        <h2 className="text-emphasis font-medium text-ink">Codebase & Context Settings</h2>
        <p className="text-body text-ink-muted">
          The codebases this workspace holds, and the instruction context and repository
          configuration applied to{" "}
          <span className="font-mono text-ink font-medium">{repoId}</span>.
        </p>
      </div>

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

      <CodebasesPanel filter={filter} />

      {/* Setting 1: Repository Context File (.sync/context.md) */}
      <SettingCard
        title="Project Context (.sync/context.md)"
        description={
          <>
            <p>
              Sync reads custom prompt instructions, architecture notes, and vendor constraints from{" "}
              <code className="font-mono text-ink font-semibold">.sync/context.md</code> directly
              within your repository.
            </p>
            <p className="text-meta text-ink-muted">
              This file versions alongside your codebase in Git, ensuring every remediation agent
              shares the same documented operational requirements as your engineering team.
            </p>
          </>
        }
        refusalNotice={
          <div className="rounded-surface border border-line bg-surface-muted/40 p-row text-meta text-ink-muted space-y-field">
            <div className="flex items-center gap-row">
              <Badge>Source of Truth: Customer Git Repository</Badge>
            </div>
            <p>
              <code className="font-mono text-ink">.sync/context.md</code> is intentionally{" "}
              <strong>read-only in the console</strong>. Sync never permits writing project context
              directly through web API endpoints, preventing prompt injection risks and ensuring
              that configuration changes are reviewed through your standard version control
              workflow.
            </p>
          </div>
        }
        control={
          <div className="flex flex-col items-end gap-row">
            <Badge>Read-only: Tracked in Git</Badge>
            <span className="font-mono text-meta text-ink-muted">Path: .sync/context.md</span>
          </div>
        }
        footer={
          <span>
            To update context, edit <code className="font-mono text-ink">.sync/context.md</code> in
            your repository and commit.
          </span>
        }
      />

      {/* Setting 2: Static Analysis Scope */}
      <SettingCard
        title="Analysis Scope & Language Grammar"
        description={
          <p>
            Sync statically analyzes TypeScript and Python dependencies to extract API call sites and
            track breaking vendor changes. Typechecking utilizes your local project lockfile and
            package manager.
          </p>
        }
        control={
          <div className="flex flex-col items-end gap-field">
            <Badge>Active</Badge>
            <span className="text-meta text-ink-muted font-mono">TypeScript / Python</span>
          </div>
        }
        footer={
          <span>
            Lockfile resolution is automatically detected from repository package manifests.
          </span>
        }
      />
    </div>
  )
}
