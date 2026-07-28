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

        The push distinguishes three cases, and the lease is what tells them
        apart:

        - The remote has no such branch. Nothing to overwrite, so the push
          carries no lease at all. If another writer creates the branch in the
          meantime, git rejects the push as a non-fast-forward, which is the
          answer we want.
        - The remote has the branch at the commit `_fetch_remote_tip` just
          observed. This is a re-run of a finding — ordinary after an
          environment fault or an earlier bug — and branch identity is derived
          from the finding, so it resolves to the branch the previous run
          pushed. The lease names that commit and the update goes through.
        - The remote has the branch at some other commit, because it moved
          between the fetch and the push. The lease names a commit that is no
          longer there and git refuses. This is the race the lease exists for,
          and it is the only thing separating this from `--force`.

        The lease settles what was observed, never whose it was, and those are
        different questions. A reviewer who pushes a fixup onto Sync's branch
        between runs has their commit fetched, observed, leased against and
        replaced. So a commit written by anyone but Sync anywhere in what this
        push would discard refuses the push outright: the finding abandons with a
        reason naming the author, which a human can act on, rather than Sync
        discarding their work on a repository it does not own.
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

        remote_tip = self._fetch_remote_tip(path, branch)
        push = ["git", "push", "-u", "origin", branch]
        if remote_tip is not None:
            # What the push would destroy: every commit the remote branch holds
            # that the commit replacing it does not carry forward. HEAD is that
            # commit, `checkout -B` and the commit above having put it there, and
            # a fixup already in HEAD's history survives the push as its parent.
            # The other end of the range is the fork from the default branch,
            # which `_fetch_remote_tip` cut rather than expressed: commits below
            # it stay reachable on the default branch whatever this push does.
            author = self._foreign_author(path, [remote_tip, "^HEAD"])
            if author is not None:
                raise RuntimeError(
                    f"{branch} carries a commit by {author}, not Sync; refusing to replace it. "
                    f"Merge or move that commit, or delete the branch, then re-run the finding."
                )
            push.append(f"--force-with-lease={branch}:{remote_tip}")
        self._run(push, path)
        return branch

    def _foreign_author(self, path: Path, discarded: list[str]) -> str | None:
        """The author of a commit in `discarded` that Sync did not write, or None
        when Sync wrote every one of them. `discarded` is a `git log` revision
        range naming the commits an operation would destroy.

        Who wrote each commit, not who committed it. Author and committer differ
        routinely, and in ways that would go against Sync: GitHub rewrites the
        committer on a squash and on any edit made through the web UI, and a
        rebase rewrites it while leaving the author alone. Reading the committer
        would call Sync's own commit a stranger's after any of those and abandon
        a finding whose branch Sync wrote every line of. The author survives all
        three, and a reviewer pushing a fixup authors it themselves.

        The range rather than the tip, because the tip is not where a stranger's
        work has to sit. A reviewer's fixup with any Sync-authored commit above
        it — a rebase, a cherry-pick, an amend that reordered — leaves a branch
        whose tip is Sync's and whose history is not, and every check shaped
        around the tip reports that the branch is Sync's to replace.

        An empty range is not a refusal. A branch Sync pushed and is updating
        with nothing else on it is the ordinary retry, and it has to keep
        working; a range expression that reports the whole branch there would
        abandon every one of them.

        This guards against clobbering human work; it is not a security control.
        `git commit --author` sets the field to anything, so anyone who can push
        to the branch can present as Sync. What stands against that is the lease
        and the customer's own branch protection, not this.
        """
        authors = self._run(["git", "log", "--format=%ae", *discarded], path).splitlines()
        return next((author for author in authors if author != COMMIT_AUTHOR_EMAIL), None)

    def delete_branch(self, repo: RepoRef, branch: str) -> tuple[bool, str]:
        """Remove a branch a finding abandoned after pushing. Returns (deleted, detail).

        Branch identity is stable per finding, so a retry no longer strands a
        branch per attempt — but a finding that abandons after its push leaves
        one behind with no pull request and nothing that will ever come back for
        it. Across a fleet those accumulate on repositories Sync does not own.

        Three things stop a deletion, and each means the branch is not Sync's to
        remove: an open pull request, because a human may be reading it right
        now; a commit on it Sync did not author, for the reason `_foreign_author`
        gives; and a remote with no such branch, which is every finding that
        abandoned before it ever pushed. The deletion carries the same lease as
        the push against the same observed tip, so a branch that moved in between
        is left alone.

        Nothing here raises, and the breadth of that is deliberate rather than
        careless: this runs after a finding has already failed, and the
        operator's useful signal is why it failed. A cleanup that raises on top
        of that replaces the reason that matters with its own.

        Which caller invokes this is the graph's decision, not the forge's — the
        forge cannot see that a run abandoned, and inferring it from the absence
        of a pull request would delete branches whose pull request simply has not
        been opened yet.
        """
        path = Path(repo.local_path)
        try:
            open_pulls = json.loads(self._run(
                [_gh(), "pr", "list", "--repo", repo.url, "--head", branch,
                 "--state", "open", "--json", "number"],
                path,
            ))
            if open_pulls:
                return False, f"{branch} has an open pull request"

            tip = self._fetch_remote_tip(path, branch)
            if tip is None:
                return False, f"the remote has no {branch}"

            # Everything the branch adds over the default branch, with nothing
            # excluded — unlike the push, which subtracts what it carries
            # forward. A deletion carries nothing forward, and a commit the clone
            # happens to hold is destroyed with the rest of them: what the clone
            # has does not keep anything reachable on the remote.
            author = self._foreign_author(path, [tip])
            if author is not None:
                return False, f"{branch} carries a commit by {author}, not Sync"

            self._run(
                ["git", "push", "origin", "--delete", branch,
                 f"--force-with-lease={branch}:{tip}"],
                path,
            )
        except Exception as exc:
            return False, f"could not delete {branch}: {exc}"
        return True, f"deleted {branch}"

    def _fetch_remote_tip(self, path: Path, branch: str) -> str | None:
        """The commit the remote has for `branch` right now, or None if it has none.

        Sync works in a shallow clone, and `--depth` implies `--single-branch`,
        so `refs/remotes/origin/<branch>` does not exist for any branch but the
        default one. A bare `--force-with-lease` reads that absence as "expect
        this ref not to exist" and rejects a branch a previous run of the same
        finding pushed. Against a ref never fetched, the lease is not a safety
        check; it is an artifact of how the clone was made.

        The expected commit is passed to the lease explicitly rather than left to
        the remote-tracking ref, because the patch agent holds `Bash` inside this
        same clone: any `git fetch` it happens to run would move that ref and
        silently turn the lease into a `--force`.

        `--shallow-exclude` asks the server for the commits this branch adds over
        the default branch and nothing else, which is both the cheapest fetch
        that answers the authorship question and the only one that answers it
        correctly. `--depth 1` brings the tip and grafts its parents away, so a
        walk of the branch stops there and cannot see whose work is underneath.
        An unbounded fetch has the opposite fault: `--depth` cut the default
        branch above the commit an older branch forks from, leaving no merge base
        to subtract, so the walk runs on into the customer's own history and
        reads their commits as ones this push would discard — which refuses every
        retry against a repository anyone else commits to. The exclusion is
        computed on the server, where the whole graph is, and it shortens a
        history as readily as it deepens one, so it holds even where something
        else in the clone has already fetched this branch in full.

        Four things land on None, and each is safe because each yields a push
        with no lease, which git accepts only as a fast-forward and otherwise
        rejects as a non-fast-forward rather than overwriting anything: the
        remote has no such branch; the branch adds nothing over the default
        branch, so the exclusion selects no commit and the server refuses the
        request; the clone records no default branch to exclude; and a fetch that
        fails for any other reason — no network, no permission.
        """
        base = self._default_branch(path)
        if base is None:
            return None
        try:
            self._run(
                ["git", "fetch", f"--shallow-exclude={base}", "origin",
                 f"+refs/heads/{branch}:refs/remotes/origin/{branch}"],
                path,
            )
        except RuntimeError:
            return None
        return self._run(["git", "rev-parse", f"refs/remotes/origin/{branch}"], path)

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
