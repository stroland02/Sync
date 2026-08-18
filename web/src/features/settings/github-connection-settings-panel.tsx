import { SettingCard } from "@/features/settings/setting-card"
import { Badge } from "@/vendor/supabase/ui/badge"

export interface GithubConnectionSettingsPanelProps {
  repoId: string
}

export function GithubConnectionSettingsPanel({ repoId }: GithubConnectionSettingsPanelProps) {
  return (
    <div className="flex flex-col gap-section">
      <div className="flex flex-col gap-field pb-field border-b border-line">
        <h2 className="text-emphasis font-medium text-ink">GitHub & Forge Connection</h2>
        <p className="text-body text-ink-muted">
          Local forge authentication and repository permission status for{" "}
          <span className="font-mono text-ink font-medium">{repoId}</span>.
        </p>
      </div>

      {/* Setting 1: Authenticated Session */}
      <SettingCard
        title="Forge Authentication (Local CLI)"
        description={
          <>
            <p>
              Sync connects to GitHub using your locally authenticated{" "}
              <code className="font-mono text-ink">gh</code> CLI session.
            </p>
            <p className="text-meta text-ink-muted">
              Pull requests, branch pushes, and CI status checks are executed using your machine&apos;s
              existing GitHub credentials. No external keys or secrets are stored in Sync.
            </p>
          </>
        }
        control={
          <div className="flex flex-col items-end gap-row">
            <Badge>Authenticated via gh CLI</Badge>
            <span className="font-mono text-meta text-ink-muted">CLI session: active</span>
          </div>
        }
        footer={
          <span>
            Verified with local <code className="font-mono text-ink">gh auth status</code>.
          </span>
        }
      />

      {/* Setting 2: Repository Permissions */}
      <SettingCard
        title="Repository Access & Branch Target"
        description={
          <p>
            Specifies the repository Sync is currently configured to monitor, remediate, and target
            for patch verification.
          </p>
        }
        control={
          <div className="flex flex-col items-end gap-field">
            <span className="font-mono text-ink text-meta font-medium">{repoId}</span>
            <Badge>Monitored Codebase</Badge>
          </div>
        }
        footer={
          <span>
            Scoped to <code className="font-mono text-ink">{repoId}</code>.
          </span>
        }
      />

      {/* Setting 3: OAuth App Status (Absent by Design) */}
      <SettingCard
        title="Hosted GitHub App OAuth (Absent by Design)"
        description={
          <>
            <p>
              Hosted OAuth application installation and external webhook callbacks are intentionally{" "}
              <strong>excluded in this local deployment</strong>.
            </p>
            <p className="text-meta text-ink-muted">
              Because Sync is built for local-first execution, it relies entirely on your local toolchain
              and authenticated CLI rather than requiring an external hosted authentication callback.
            </p>
          </>
        }
        refusalNotice={
          <div className="rounded-surface border border-line bg-surface-muted/40 p-row text-meta text-ink-muted space-y-field">
            <div className="flex items-center gap-row">
              <Badge>Local-Only Architecture</Badge>
            </div>
            <p>
              Hosted OAuth callback endpoints are deliberately not implemented. Sync does not hold
              customer secrets or expose open web listeners.
            </p>
          </div>
        }
        control={
          <div className="flex flex-col items-end gap-row">
            <Badge>Local Mode</Badge>
            <span className="text-meta text-ink-muted">OAuth flow not required</span>
          </div>
        }
        footer={
          <span>
            Operating in self-contained local workspace mode.
          </span>
        }
      />
    </div>
  )
}
