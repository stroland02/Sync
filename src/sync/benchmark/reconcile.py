"""Reconciling migration outcome rows against GitHub pull request states.

`open_pull_request` records the pull request number and ends the run. A pull request merges
days later, or never, and until something asks GitHub what became of it, `pr_merged` stays null
on every corpus row and the merge rate -- the direct test of the product claim -- has no numerator.

This is the pull-side updater that pairs with `sync.forge.webhook.record_merge_outcome`: it asks
`GitHubForge.pull_request_outcome` for each open pull request, resolves the repository for the
underlying finding, and records the verified merge outcome with GitHub's exact `mergedAt` timestamp.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from typing import Any

from sync.core import MigrationOutcome, RepoRef
from sync.forge.github import GitHubForge, PullRequestOutcome
from sync.graph.store import GraphStore

log = logging.getLogger(__name__)

RepoResolver = Callable[[str], RepoRef | None] | Mapping[str, RepoRef]


def _resolve_repo(repo_resolver: RepoResolver, repo_id: str) -> RepoRef | None:
    if callable(repo_resolver):
        return repo_resolver(repo_id)
    return repo_resolver.get(repo_id)


def reconcile_pull_request_outcomes(
    store: GraphStore,
    forge: GitHubForge,
    repo_resolver: RepoResolver,
) -> list[tuple[MigrationOutcome, PullRequestOutcome]]:
    """Ask GitHub what became of every open pull request in the corpus and update the store.

    Finds every production `migration_outcome` row with `pr_number` set and `pr_merged` still
    `None`. For each row, resolves the `repo_id` through the finding's call site in the graph,
    looks up the `RepoRef` from `repo_resolver`, queries `forge.pull_request_outcome(repo, pr_number)`,
    and updates the row via `store.set_merge_outcome`.

    Returns the list of (outcome, pr_outcome) pairs that were updated.
    """
    pending = store.pending_merge_outcomes()
    if not pending:
        return []

    finding_ids = [row.finding_id for row in pending]
    repo_ids = store.repo_ids_for_findings(finding_ids)

    updated: list[tuple[MigrationOutcome, PullRequestOutcome]] = []
    for row in pending:
        if row.pr_number is None:
            continue
        repo_id = repo_ids.get(row.finding_id) or store.repo_id_for_finding(row.finding_id)
        if not repo_id:
            log.warning("cannot reconcile finding %s: no repo_id found in graph", row.finding_id)
            continue
        repo = _resolve_repo(repo_resolver, repo_id)
        if repo is None:
            log.warning(
                "cannot reconcile finding %s: no RepoRef resolved for repo_id %s",
                row.finding_id,
                repo_id,
            )
            continue

        try:
            pr_outcome = forge.pull_request_outcome(repo, row.pr_number)
        except Exception as exc:
            log.warning("failed to query GitHub for %s PR #%s: %s", repo_id, row.pr_number, exc)
            continue

        # If GitHub returned a decided outcome (merged is True or False):
        if pr_outcome.merged is not None:
            store.set_merge_outcome(
                finding_id=row.finding_id,
                attempt_index=row.attempt_index,
                pr_number=row.pr_number,
                pr_merged=pr_outcome.merged,
                human_edits_before_merge=pr_outcome.commits_by_others,
                pr_merged_at=pr_outcome.merged_at,
            )
            updated.append((row, pr_outcome))

    return updated
