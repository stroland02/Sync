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
# toward one.
NON_BLOCKING_CONCLUSIONS = frozenset({"skipped", "neutral"})

# Sync authors this commit inside a clone of a repository it does not own, so
# the identity is supplied per-invocation via `git -c` and never written into
# the clone's config or inherited from the host machine's global git config.
# `git -c <key>=<value>` is a general config-override mechanism and some keys
# execute commands (`core.pager`, `core.editor`) — safe here only because both
# values below are module constants, never caller- or vendor-supplied.
COMMIT_AUTHOR_NAME = "Sync"
COMMIT_AUTHOR_EMAIL = "sync@users.noreply.github.com"


def _gh() -> str:
    found = shutil.which("gh")
    if found is None:
        raise FileNotFoundError("gh CLI not found on PATH")
    return found


def _owner_repo(url: str) -> str:
    """`gh api` addresses a repository as `owner/name`, which `RepoRef` carries
    only as part of a clone URL: after the host for an HTTPS remote, after a
    colon for an SSH one."""
    trimmed = url.rstrip("/").removesuffix(".git")
    segments = trimmed.replace(":", "/").split("/")
    return f"{segments[-2]}/{segments[-1]}"


def branch_name_for(patch: Patch, repo: RepoRef) -> str:
    """One branch per finding, stable across that finding's CI retries.

    `patch.rationale` rather than `patch.diff`: a retry's diff is only the
    increment on top of the attempt already committed on the branch, so a
    diff-derived name resolves somewhere new on every attempt and each retry
    strands a pushed branch on a repository Sync does not own. A remediator
    copies the finding's rationale into every patch it proposes for that
    finding, which makes it the identity available here — `Patch` carries no
    finding id and the `Forge` protocol passes no finding. A remediator that
    regenerates rationale text per attempt would reintroduce the stranded
    branches, which is what
    `test_a_patch_carries_its_findings_rationale_verbatim` exists to catch.
    """
    digest = hashlib.sha256(f"{repo.repo_id}|{patch.rationale}".encode("utf-8")).hexdigest()[:12]
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

Where Sync can read the base branch's required status checks, the run linked
above is one of them. Reading them needs repository admin rights, and where Sync
cannot, it accepts any successful run for the commit — which a workflow
unrelated to this change can satisfy. Check that the linked run is the one that
verifies this repository.

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
        self._run(
            ["git", "-c", f"user.name={COMMIT_AUTHOR_NAME}", "-c", f"user.email={COMMIT_AUTHOR_EMAIL}",
             "commit", "-m", f"fix: {patch.rationale}"],
            path,
        )
        self._run(["git", "push", "-u", "origin", branch, "--force-with-lease"], path)
        return branch

    def _default_branch(self, path: Path) -> str | None:
        """`origin/HEAD` records the default branch as of the clone, which costs
        no API call and cannot be confused with the branch Sync just pushed."""
        try:
            ref = self._run(["git", "rev-parse", "--abbrev-ref", "origin/HEAD"], path)
        except RuntimeError:
            return None
        return ref.removeprefix("origin/") or None

    def _required_contexts(self, repo: RepoRef, path: Path) -> frozenset[str] | None:
        """The checks that must pass for a pull request to merge, or None when
        Sync cannot learn which those are.

        Protection is read for the default branch, not for the branch Sync
        pushed: required checks are configured on the branch a pull request
        merges into, and a `sync/api-drift-*` branch created seconds ago is
        unprotected by construction.

        None is a documented hole, not a preference. With no check named,
        `await_ci` accepts any successful run, which an always-green workflow —
        a labeler, a title linter — satisfies while the workflow that would
        have caught a bad patch is gated off for this push. Two ordinary
        situations produce it: a default branch carrying no protection rule
        (404), and a `gh` token that is not a repository admin, which this
        endpoint requires (403). Erring red instead would stop Sync opening a
        pull request against any repository in that second group. A transient
        `gh` failure is indistinguishable from either here and downgrades the
        gate for the whole wait, since this is read once per `await_ci`.
        """
        base = self._default_branch(path)
        if base is None:
            return None
        try:
            raw = self._run(
                [_gh(), "api",
                 f"repos/{_owner_repo(repo.url)}/branches/{base}/protection/required_status_checks"],
                path,
            )
        except RuntimeError:
            return None
        payload = json.loads(raw)
        # `contexts` is the flat form and `checks` the one that also carries the
        # app id; GitHub documents the first as deprecated in favour of the
        # second and repositories are served either.
        contexts = payload.get("contexts") or [check["context"] for check in payload.get("checks") or []]
        return frozenset(contexts) or None

    def _checks_for(
        self, repo: RepoRef, branch: str, head: str, path: Path, required: frozenset[str] | None
    ) -> list[dict]:
        """Everything that counts as verification of `head`, as `name`, `status`,
        `conclusion`, `url`.

        Two sources, because a required status check names a job and `gh run
        list` reports only the workflow containing it. Knowing which checks
        count, Sync asks for the commit's check runs by name; not knowing, it
        falls back to the workflow runs on the branch, filtered to this commit
        — a run left over from an earlier push to the same branch says nothing
        about this patch.

        One page of each is read. A commit carrying more than 100 check runs
        would look to `await_ci` as though a required one had not reported,
        which holds the patch back rather than letting it through.
        """
        if required is None:
            raw = self._run(
                [_gh(), "run", "list", "--branch", branch, "--limit", "50",
                 "--json", "status,conclusion,url,headSha,workflowName"],
                path,
            )
            return [
                {"name": run["workflowName"], "status": run["status"],
                 "conclusion": run["conclusion"], "url": run["url"]}
                for run in json.loads(raw) if run["headSha"] == head
            ]

        raw = self._run(
            [_gh(), "api", f"repos/{_owner_repo(repo.url)}/commits/{head}/check-runs?per_page=100"],
            path,
        )
        return [
            {"name": check["name"], "status": check["status"],
             "conclusion": check["conclusion"], "url": check["html_url"]}
            for check in json.loads(raw)["check_runs"] if check["name"] in required
        ]

    def await_ci(self, repo: RepoRef, branch: str) -> tuple[bool, str]:
        """Poll the checks that verify the pushed commit. Returns (green, detail).

        Green requires every check that counts to have completed, at least one
        of them to have concluded `success`, none to have concluded in a
        blocking state (see `NON_BLOCKING_CONCLUSIONS`), and the same set to
        hold on a second, later poll. Which checks count comes from the base
        branch's required status checks where Sync can read them and from every
        workflow run for the commit where it cannot — `_required_contexts`
        states what the second case is unable to rule out.

        The second poll matters for a chained layout: a workflow triggered by
        `workflow_run: types: [completed]` gets its run record only once the
        workflow it depends on finishes. A poll landing in that gap sees one
        green run and nothing else, which without re-confirming reads as a
        verdict on a commit whose second workflow has not started. Read the
        other way round, the same confirmation ends a run that can never go
        green: a stable set with no success and no failure has nothing left to
        wait for, and polling on to the deadline spends the customer's CI
        window and one further patch attempt to learn what is already settled.
        A red verdict needs no confirmation at all, since waiting cannot make a
        failure not have happened.

        On green the detail is the URL a reviewer clicks and on red the URL of a
        check that did not pass. Both are chosen by sorting rather than by list
        position: `gh` orders runs by id, which says nothing about which run
        verified anything, and two attempts against one commit must not cite
        different runs. Where required checks are known, only they are
        candidates, so the URL points at a check that had to pass.

        Four timeout messages, since each implies a different fix: nothing ever
        appeared for this commit (no workflow triggers on `push`), a required
        check never reported (that job does not run on `push`), checks appeared
        but had not all finished (CI is slow or hung), or everything finished
        without a confirmed green verdict (a lone green run one poll short of
        stable). An unverifiable patch must never reach a pull request whichever
        applies.
        """
        path = Path(repo.local_path)
        head = self._run(["git", "rev-parse", "HEAD"], path)
        required = self._required_contexts(repo, path)
        deadline = time.monotonic() + self._timeout

        # What the last poll saw, not what any poll ever saw. A workflow can
        # appear several polls in, and the timeout message is an operator's
        # account of where the run actually stopped.
        observed = "none"
        missing: frozenset[str] = frozenset()
        stable: frozenset[tuple[str, str | None]] | None = None

        while time.monotonic() < deadline:
            checks = self._checks_for(repo, branch, head, path, required)
            if required is not None:
                missing = required - {check["name"] for check in checks}

            if not checks and not missing:
                observed, stable = "none", None
                time.sleep(self._poll)
                continue

            if missing:
                observed, stable = "missing", None
                time.sleep(self._poll)
                continue

            if not all(check["status"] == "completed" for check in checks):
                observed, stable = "running", None
                time.sleep(self._poll)
                continue

            observed = "completed"

            failing = [
                check for check in checks
                if check["conclusion"] not in NON_BLOCKING_CONCLUSIONS
                and check["conclusion"] != "success"
            ]
            if failing:
                return False, min(check["url"] for check in failing)

            current = frozenset((check["url"], check["conclusion"]) for check in checks)
            if current != stable:
                stable = current
                time.sleep(self._poll)
                continue

            succeeded = [check for check in checks if check["conclusion"] == "success"]
            if succeeded:
                return True, min(check["url"] for check in succeeded)
            return False, f"nothing verified {head[:12]}: " + ", ".join(
                f"{check['name']} concluded {check['conclusion']}"
                for check in sorted(checks, key=lambda check: check["name"])
            )

        if observed == "none":
            return False, f"no completed CI run for {head[:12]} within {self._timeout}s"
        if observed == "missing":
            return False, (
                f"required check(s) {', '.join(sorted(missing))} never reported for "
                f"{head[:12]} within {self._timeout}s"
            )
        if observed == "running":
            return False, f"CI for {head[:12]} was still running at the {self._timeout}s deadline"
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
