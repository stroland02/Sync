/**
 * The file tree's opening facts: how large this codebase is, and how long it has existed.
 *
 * **The census is a measurement of the tree, not of Sync's work**, and every note says which.
 * Files and lines come from `git ls-files` and a newline count over bytes — what is tracked,
 * never what is on disk — so a generated directory that git ignores is absent by design and an
 * untracked scratch file does not inflate the count.
 *
 * **Lines are counted over bytes rather than parsed**, which is why binary files are counted
 * separately and excluded from the line total rather than contributing a meaningless number.
 *
 * **Nothing here is a productivity figure.** Commits and contributors are facts about the
 * repository's history that make the tree above legible — a hundred-file codebase with four
 * commits reads differently from one with four thousand — and neither is a rate, a velocity, or
 * a per-person anything. `codebase-facts-card.tsx` carries the same refusal in full.
 *
 * **A null from git is not a zero.** The census runs `git` and records what it answered; where a
 * count is null the command did not answer, which is a different fact from a repository with no
 * commits, and the tile says so rather than printing nought.
 */

import { useQuery } from "@tanstack/react-query"

import { fetchFacts } from "@/features/repositories/codebase-facts-card"
import { KpiStrip } from "@/components/kpi-strip"
import { RelativeTime } from "@/components/relative-time"
import { Absent } from "@/components/status"
import { ErrorState, LoadingState } from "@/components/states"

export function CodebaseFactsKpis({ repoId }: { repoId: string }) {
  const query = useQuery({
    // The census card's key, so the strip and the card at the foot of the page are one read.
    queryKey: ["codebase-facts", repoId],
    queryFn: ({ signal }) => fetchFacts(repoId, signal),
  })

  if (query.isPending) return <LoadingState what="the codebase census" />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what="the codebase census"
        onRetry={() => void query.refetch()}
      />
    )
  }

  const facts = query.data.facts
  if (facts === null) {
    return (
      <KpiStrip
        items={[
          {
            label: "Files tracked",
            value: <Absent>no census recorded</Absent>,
            note: "the index has not measured this codebase",
            figure: false,
          },
          {
            label: "Lines",
            value: <Absent>no census recorded</Absent>,
            note: "nothing to count until one runs",
            figure: false,
          },
          {
            label: "Languages",
            value: <Absent>no census recorded</Absent>,
            note: "the tree above is drawn from call sites, which is a different read",
            figure: false,
          },
        ]}
      />
    )
  }

  const lines = facts.languages.reduce((sum, language) => sum + language.lines, 0)

  return (
    <KpiStrip
      items={[
        {
          label: "Files tracked",
          value: facts.total_files.toLocaleString(),
          // Tracked, not present: an ignored build directory is absent by design.
          note: `git-tracked${facts.binary_files > 0 ? `, ${facts.binary_files.toLocaleString()} of them binary` : ""}`,
        },
        {
          label: "Lines",
          value: lines.toLocaleString(),
          note: "counted over bytes in text files, binaries excluded",
        },
        {
          label: "Languages",
          value: facts.languages.length.toLocaleString(),
          note:
            facts.languages.length === 0
              ? "no file matched a known extension"
              : `led by ${facts.languages[0].name}`,
        },
        {
          label: "First commit",
          value:
            facts.git.first_commit_at === null ? (
              <Absent>git did not answer</Absent>
            ) : (
              <RelativeTime iso={facts.git.first_commit_at} />
            ),
          note:
            facts.git.commit_count === null
              ? "so the commit count is unknown rather than nought"
              : `${facts.git.commit_count.toLocaleString()} commits since`,
          figure: false,
        },
      ]}
    />
  )
}
