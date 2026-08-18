import { SettingCard } from "@/features/settings/setting-card"
import { Badge } from "@/vendor/supabase/ui/badge"

export interface CodebasesSettingsPanelProps {
  repoId: string
}

export function CodebasesSettingsPanel({ repoId }: CodebasesSettingsPanelProps) {
  return (
    <div className="flex flex-col gap-section">
      <div className="flex flex-col gap-1 pb-field border-b border-line">
        <h2 className="text-emphasis font-medium text-ink">Codebase & Context Settings</h2>
        <p className="text-body text-ink-muted">
          Instruction context and repository configuration for{" "}
          <span className="font-mono text-ink font-medium">{repoId}</span>.
        </p>
      </div>

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
          <div className="rounded-surface border border-line bg-surface-muted/40 p-3 text-meta text-ink-muted space-y-1">
            <div className="flex items-center gap-2">
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
          <div className="flex flex-col items-end gap-2">
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
          <div className="flex flex-col items-end gap-1">
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
