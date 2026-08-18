/**
 * The technical census: what this codebase is made of, measured at index time.
 *
 * The owner's direction 2026-08-18: the Overview should carry real software-engineering
 * information about the codebase itself, the way the Codebases settings panel talks about the
 * stack. The build-versus-buy note (`references/notes/codebase-facts-tooling.md`) records why
 * this reads our own census rather than shipping a line-counting binary: the index already
 * walks the tree, the intake already parses manifests, and git answers its own history.
 *
 * Every figure names its method through the ⓘ: files are the repository's own `git ls-files`
 * answer, lines are newline counts over bytes, the stack is what the manifests declare. A
 * repository with no census yet says so and names the command that produces one — absence,
 * never a screen quietly missing.
 */

import { useQuery } from "@tanstack/react-query"

import {
  ApiStatusError,
  MalformedResponseError,
  UnreachableApiError,
} from "@/api/errors"
import { InfoHint } from "@/components/info-hint"
import { MetricPanel } from "@/components/metric-panel"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { RelativeTime } from "@/components/relative-time"

interface LanguageFact {
  name: string
  files: number
  lines: number
}

interface CodebaseFacts {
  census: string
  total_files: number
  binary_files: number
  languages: LanguageFact[]
  git: {
    commit_count: number | null
    first_commit_at: string | null
    last_commit_at: string | null
    contributor_count: number | null
  }
  dependencies: {
    by_ecosystem: Record<string, string[]>
    unreadable_manifests: string[]
  }
  toolchain: string[]
  computed_at: string
}

interface FactsResponse {
  repo_id: string
  facts: CodebaseFacts | null
}

async function fetchFacts(repoId: string, signal?: AbortSignal): Promise<FactsResponse> {
  const path = `/api/repositories/${encodeURIComponent(repoId)}/facts`
  let response: Response
  try {
    response = await fetch(path, { headers: { Accept: "application/json" }, signal })
  } catch (cause) {
    if (signal?.aborted) throw cause
    throw new UnreachableApiError(path, { cause })
  }
  if (!response.ok) throw new ApiStatusError(response.status, path)
  try {
    return (await response.json()) as FactsResponse
  } catch (cause) {
    throw new MalformedResponseError(path, { cause })
  }
}

function GitFact({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-field">
      <span className="furniture text-meta text-ink-muted">{label}</span>
      <span className="font-mono text-body text-ink">{value}</span>
    </div>
  )
}

export function CodebaseFactsCard({ repoId }: { repoId: string }) {
  const query = useQuery({
    queryKey: ["codebase-facts", repoId],
    queryFn: ({ signal }) => fetchFacts(repoId, signal),
  })

  if (query.isPending) return <LoadingState what={`the technical census of ${repoId}`} />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what={`the technical census of ${repoId}`}
        onRetry={() => void query.refetch()}
      />
    )
  }

  const facts = query.data.facts
  if (facts === null) {
    return (
      <EmptyState
        headline="No technical census yet."
        detail="The census is computed when the index walks this codebase, and no pass has run since it existed. `uv run sync index --repo .` produces one."
      />
    )
  }

  const topLanguages = facts.languages.filter((language) => language.name !== "other").slice(0, 8)
  const ecosystems = Object.entries(facts.dependencies.by_ecosystem)

  return (
    <MetricPanel
      label="Technical census"
      hint={
        <InfoHint label="About the technical census">
          Measured when the index last walked this checkout, with each figure&rsquo;s method
          stated: files are the repository&rsquo;s own {facts.census} answer, lines are newline
          counts over bytes (binaries counted as files, never as lines), the stack is what the
          manifests themselves declare, and the history figures are git&rsquo;s own.
        </InfoHint>
      }
      metric={{
        value: facts.total_files.toLocaleString(),
        unit: `tracked files, censused by ${facts.census}`,
      }}
      caption={
        <p className="max-w-prose">
          Computed <RelativeTime iso={facts.computed_at} /> with the index pass, so the census
          describes the same tree the call sites came from.
        </p>
      }
    >
      <div className="grid gap-section lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <div className="flex min-w-0 flex-col gap-row">
          <h3 className="furniture text-meta text-ink-muted">Languages</h3>
          <div className="grid grid-cols-[minmax(0,1fr)_auto_auto] gap-x-section gap-y-field">
            <span className="furniture text-meta text-ink-muted">name</span>
            <span className="furniture text-right text-meta text-ink-muted">files</span>
            <span className="furniture text-right text-meta text-ink-muted">lines</span>
            {topLanguages.map((language) => (
              <LanguageRow key={language.name} language={language} />
            ))}
          </div>
        </div>

        <div className="flex min-w-0 flex-col gap-section">
          <div className="flex flex-col gap-row">
            <h3 className="furniture text-meta text-ink-muted">History</h3>
            <div className="grid grid-cols-2 gap-section">
              <GitFact
                label="Commits"
                value={facts.git.commit_count?.toLocaleString() ?? "—"}
              />
              <GitFact
                label="Contributors"
                value={facts.git.contributor_count?.toLocaleString() ?? "—"}
              />
              <GitFact
                label="First commit"
                value={
                  facts.git.first_commit_at !== null ? (
                    <RelativeTime iso={facts.git.first_commit_at} />
                  ) : (
                    "—"
                  )
                }
              />
              <GitFact
                label="Last commit"
                value={
                  facts.git.last_commit_at !== null ? (
                    <RelativeTime iso={facts.git.last_commit_at} />
                  ) : (
                    "—"
                  )
                }
              />
            </div>
          </div>

          <div className="flex flex-col gap-row">
            <h3 className="furniture text-meta text-ink-muted">Toolchain</h3>
            <div className="flex flex-wrap gap-field">
              {facts.toolchain.length === 0 && (
                <span className="text-meta text-ink-muted">no recognised toolchain markers</span>
              )}
              {facts.toolchain.map((tool) => (
                <span
                  key={tool}
                  className="furniture rounded-control border border-line px-field py-field text-meta text-ink-muted"
                >
                  {tool}
                </span>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-row">
            <h3 className="furniture text-meta text-ink-muted">Declared dependencies</h3>
            {ecosystems.length === 0 ? (
              <span className="text-meta text-ink-muted">
                no parseable manifest declares any
              </span>
            ) : (
              ecosystems.map(([ecosystem, names]) => (
                <p key={ecosystem} className="min-w-0 text-meta text-ink-muted">
                  <span className="font-mono text-ink">{ecosystem}</span>: {names.length}{" "}
                  {names.length === 1 ? "package" : "packages"} —{" "}
                  <span className="font-mono">{names.slice(0, 6).join(", ")}</span>
                  {names.length > 6 && ` and ${names.length - 6} more`}
                </p>
              ))
            )}
            {facts.dependencies.unreadable_manifests.length > 0 && (
              <p className="max-w-prose text-meta text-ink-muted">
                Could not parse:{" "}
                <span className="font-mono">
                  {facts.dependencies.unreadable_manifests.join(", ")}
                </span>{" "}
                — those manifests are a gap in this list, not an empty declaration.
              </p>
            )}
          </div>
        </div>
      </div>
    </MetricPanel>
  )
}

function LanguageRow({ language }: { language: LanguageFact }) {
  return (
    <>
      <span className="min-w-0 truncate text-body text-ink">{language.name}</span>
      <span className="text-right font-mono text-body tabular-nums text-ink">
        {language.files.toLocaleString()}
      </span>
      <span className="text-right font-mono text-body tabular-nums text-ink-muted">
        {language.lines.toLocaleString()}
      </span>
    </>
  )
}
