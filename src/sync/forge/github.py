"""Git and GitHub operations via the authenticated `gh` CLI.

`gh` is used rather than a REST client because it is already installed and
authenticated on developer machines, which keeps M0 free of a separate token
management story. The hosted control plane at M4 will need a GitHub App instead.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

from sync.core import Evidence, Patch, RepoRef

# `skipped` (an `if:`-gated job) and `neutral` indicate a run verified
# nothing, not that it failed. They neither block a green verdict nor count
# toward one, matching how GitHub's own branch protection resolves them.
NON_BLOCKING_CONCLUSIONS = frozenset({"skipped", "neutral"})


def _gh() -> str:
    found = shutil.which("gh")
    if found is None:
        raise FileNotFoundError("gh CLI not found on PATH")
    return found


def branch_name_for(patch: Patch, repo: RepoRef) -> str:
    digest = hashlib.sha256(f"{repo.repo_id}|{patch.diff}".encode()).hexdigest()[:12]
    return f"sync/api-drift-{digest}"


def render_pr_body(evidence: Evidence) -> str:
    sites = "\n".join(f"- `{site}`" for site in evidence.call_sites)
    return f"""## What changed upstream

{evidence.changelog_entry}

```json
{json.dumps(evidence.spec_diff, indent=2, ensure_ascii=False)}
```

## Affected call sites

{sites}

## Verification

CI passed on this branch before the pull request was opened: {evidence.ci_run_url}

---

Opened by **Sync**. Nothing reaches a pull request without a green CI run on the
branch — if this is wrong, the verification gate is what needs fixing, not just
this diff.
"""


class GitHubForge:
    def __init__(self, poll_interval_seconds: int = 15, timeout_seconds: int = 1800) -> None:
        self._poll = poll_interval_seconds
        self._timeout = timeout_seconds

    def _run(self, args: list[str], cwd: Path) -> str:
        result = subprocess.run(
            args, cwd=cwd, capture_output=True, text=True, encoding="utf-8"
        )
        if result.returncode != 0:
            raise RuntimeError(f"{' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def push_branch(self, repo: RepoRef, patch: Patch) -> str:
        """Commit the tracked changes and push them. The patch is already applied on disk.

        `git add -u` rather than `-A`: the patch came from `git diff`, which sees
        tracked modifications only, so staging untracked files would commit
        whatever the agent's tool calls happened to leave behind — a build
        directory, a log, a stray dependency install — none of which the patch
        or the review evidence describes.

        The graph guarantees a non-empty diff before this runs, so `git commit`
        cannot fail here for an empty index.
        """
        path = Path(repo.local_path)
        branch = branch_name_for(patch, repo)
        self._run(["git", "checkout", "-B", branch], path)
        self._run(["git", "add", "-u"], path)
        self._run(["git", "commit", "-m", f"fix: {patch.rationale}"], path)
        self._run(["git", "push", "-u", "origin", branch, "--force-with-lease"], path)
        return branch

    def await_ci(self, repo: RepoRef, branch: str) -> tuple[bool, str]:
        """Poll every workflow run for the pushed commit. Returns (green, detail).

        Green requires at least one run concluding `success`, no run
        concluding in a blocking state (see `NON_BLOCKING_CONCLUSIONS`), and
        the same set of successful run URLs holding on a second, later poll.
        `--limit 1` would report whichever workflow started last, so a
        repository whose lint job passes and whose test job fails would read
        as green. A commit whose only runs are skipped or neutral has nothing
        confirming it and stays red at the timeout — the "at least one
        success" half of the rule, not just "no failures", is what keeps a
        gated or filtered workflow from reading as verified when nothing ran.

        The second poll matters for a chained layout — a workflow triggered by
        `workflow_run: types: [completed]` gets its run record only after the
        workflow it depends on finishes. A poll landing in that gap sees one
        green run and nothing else; without re-confirming, that reads as a
        verdict on a commit whose second workflow hasn't even started yet.
        A red verdict is not subject to this: an unsuccessful run is red the
        moment it is seen, since waiting cannot make a failure not have happened.

        Filtering on `headSha` matters for the same reason as the run-set
        check: a run left over from an earlier push to the same branch says
        nothing about this patch.

        On red, the returned URL points at a run that did not succeed. `gh run
        list` orders by run id, which carries no relevance to a human
        reviewer, so the first entry in the list cannot be assumed useful.

        Three timeout messages, not one, since each implies a different fix:
        no run ever appeared for this commit (nothing triggers on `push`),
        runs appeared but some never finished (CI is slow or hung), or every
        run finished without ever producing a confirmed green verdict (a lone
        green run one poll short of stable, or a commit where nothing but
        skips and neutrals ever ran). An unverifiable patch must never reach a
        pull request regardless of which of the three applies.
        """
        path = Path(repo.local_path)
        head = self._run(["git", "rev-parse", "HEAD"], path)
        deadline = time.monotonic() + self._timeout
        gh = _gh()

        saw_a_run_for_head = False
        saw_all_completed = False
        stable_success_urls: frozenset[str] | None = None

        while time.monotonic() < deadline:
            raw = self._run(
                [gh, "run", "list", "--branch", branch, "--limit", "50",
                 "--json", "status,conclusion,url,headSha"],
                path,
            )
            runs = [run for run in json.loads(raw) if run["headSha"] == head]

            if not runs:
                stable_success_urls = None
                time.sleep(self._poll)
                continue

            saw_a_run_for_head = True

            if not all(run["status"] == "completed" for run in runs):
                stable_success_urls = None
                time.sleep(self._poll)
                continue

            saw_all_completed = True

            failing = [
                run for run in runs
                if run["conclusion"] not in NON_BLOCKING_CONCLUSIONS and run["conclusion"] != "success"
            ]
            if failing:
                return False, failing[0]["url"]

            succeeded = [run for run in runs if run["conclusion"] == "success"]
            if not succeeded:
                stable_success_urls = None
                time.sleep(self._poll)
                continue

            current_success_urls = frozenset(run["url"] for run in succeeded)
            if current_success_urls == stable_success_urls:
                return True, succeeded[0]["url"]
            stable_success_urls = current_success_urls
            time.sleep(self._poll)

        if not saw_a_run_for_head:
            return False, f"no completed CI run for {head[:12]} within {self._timeout}s"
        if not saw_all_completed:
            return False, f"CI runs for {head[:12]} started but never all completed within {self._timeout}s"
        return False, f"CI for {head[:12]} completed without a confirmed green verdict within {self._timeout}s"

    def open_pull_request(self, repo: RepoRef, branch: str, evidence: Evidence) -> str:
        """Open the PR against `repo.url`, not whatever `gh` would infer from
        the clone's remotes. On a forked clone that inference resolves to the
        fork's parent — a repository Sync does not own and must not write to."""
        path = Path(repo.local_path)
        return self._run(
            [_gh(), "pr", "create",
             "--repo", repo.url,
             "--title", f"fix: {evidence.changelog_entry[:60]}",
             "--body", render_pr_body(evidence),
             "--head", branch],
            path,
        )
