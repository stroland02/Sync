"""Read mined migration commits and report what they are, before anyone labels with them.

`docs/superpowers/specs/2026-07-28-sync-ground-truth-count.md` settled sample size and left
label quality open. It inferred agent authorship from message uniformity -- formulaic,
multilingual subjects across zero-star repositories created weeks before the commit -- which is
suggestive and is not proof. This is the instrument for the proof, and
`2026-07-29-sync-ground-truth-quality.md` is what it was pointed at.

A sibling of `mine_stripe_migrations.py` rather than an addition to it, because it asks a
different question. That one reduces a search response to a total: how many are there. This one
reads one commit at a time and reports who wrote it and what it touched. The fixtures differ,
the pure functions differ, and folding them together would give one module two reasons to
change.

What it does not do
-------------------
It clones nothing, checks out no parent commit, and runs no part of Sync's pipeline. The
benchmark spec's sequencing rule -- do not build the harness before running the count -- still
binds, and this exists because the count raised a question the count could not answer.

Signals, not verdicts
---------------------
Every function here reports what it observed. Whether a cohort can serve as ground truth is a
judgement made in a document by a human reading the numbers, and a classifier that returned
`is_ground_truth` would be that judgement hidden in a boolean somebody later trusts without
reading how it was reached.

The same split as the counting instrument
-----------------------------------------
Fetching shells out to `gh` and touches the network, so no test drives it. Reading takes parsed
JSON and returns a structure. And the distinction that matters most is inherited whole: a
rate-limited response is not a commit that changed nothing. A reader answering "no files" to an
exhausted token turns a measurement failure into a finding.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from typing import Any

MEASURED = "measured"
UNMEASURABLE = "unmeasurable"

# Identities that say a machine wrote the patch. Matched against co-author trailers and against
# the author and committer logins. `[bot]` is GitHub's own suffix for an App; the rest are the
# agents this cohort actually carries, taken from the trailers observed rather than guessed.
AGENT_IDENTITY = re.compile(
    r"(?i)\bclaude\b|\bcopilot\b|\bcursor\b|\bdevin\b|\bcodex\b|\baider\b|\bwindsurf\b"
    r"|dependabot|renovate|\[bot\]|swe-agent"
)

_TRAILER = re.compile(r"(?im)^co-authored-by:\s*(.+)$")

# The pinned version, in every spelling the SDKs use: `apiVersion` in the JavaScript and
# TypeScript constructors, `api_version` in Python and Ruby, `API_VERSION` as a constant.
PIN_LINE = re.compile(r"(?i)api[_-]?version")

# Files that carry a dependency's version rather than a call site. A lockfile moving beside a
# pin is a dependency bump wearing a migration's shape, and it is the largest and least
# informative group in this cohort.
DEPENDENCY_FILE = re.compile(
    r"(?i)(^|/)(package(-lock)?\.json|yarn\.lock|pnpm-lock\.yaml|Gemfile(\.lock)?"
    r"|requirements\.txt|poetry\.lock|composer\.(json|lock)|go\.(mod|sum))$"
)

# Where a call site can live. Deliberately an allow-list: a deny-list would count a README, a
# changelog and a `.env.example` as code the moment somebody added a file type nobody listed.
SOURCE_FILE = re.compile(r"(?i)\.(ts|tsx|js|jsx|mjs|cjs|py|rb|go|php|java|cs|kt|rs)$")


@dataclass(frozen=True)
class Authorship:
    """Who the commit says wrote it.

    `trailers` is kept verbatim rather than reduced to a flag, because the trailer is the
    evidence: "65% carry an agent trailer" is a claim a reader can challenge only if the strings
    behind it are quotable.
    """

    agent_trailer: bool
    bot_identity: bool
    trailers: tuple[str, ...]
    author_login: str | None
    committer_login: str | None

    @property
    def any_agent_signal(self) -> bool:
        return self.agent_trailer or self.bot_identity


@dataclass(frozen=True)
class DiffShape:
    """What the commit touched, in the terms the benchmark's question is asked in."""

    files_changed: int
    touches_pin: bool
    call_site_files: tuple[str, ...]
    changed_lines: int

    @property
    def pin_only(self) -> bool:
        """Whether the pin moved and no call site did.

        Not a migration. It either compiled by luck or broke silently, and as a labelled patch
        it says the correct answer to a breaking release is to touch no call site -- the
        opposite of what binding precision and recall would be scored against.
        """
        return self.touches_pin and not self.call_site_files


@dataclass(frozen=True)
class CommitReading:
    """One commit read, or a stated inability to read it."""

    repo: str
    sha: str
    outcome: str
    detail: str
    subject: str = ""
    authorship: Authorship | None = None
    diff: DiffShape | None = None

    @property
    def is_final(self) -> bool:
        return self.outcome == MEASURED


def classify_authorship(commit: dict[str, Any]) -> Authorship:
    """The authorship signals a commit carries, without deciding what they mean.

    Three of them, and they fail differently. A co-author trailer is a written statement and the
    strongest; a `Bot` account type is GitHub's own classification; a login matching a known
    agent catches the case where a human account is driven by one. A commit carrying none of the
    three is *unsignalled*, which is not the same as human-authored -- an agent leaving no
    trailer looks exactly like a person.
    """
    message = (commit.get("commit") or {}).get("message") or ""
    trailers = tuple(match.group(1).strip() for match in _TRAILER.finditer(message))

    author = commit.get("author") or {}
    committer = commit.get("committer") or {}
    logins = f"{author.get('login') or ''} {committer.get('login') or ''}"

    return Authorship(
        agent_trailer=any(AGENT_IDENTITY.search(trailer) for trailer in trailers),
        bot_identity=(
            author.get("type") == "Bot"
            or committer.get("type") == "Bot"
            or bool(AGENT_IDENTITY.search(logins))
        ),
        trailers=trailers,
        author_login=author.get("login"),
        committer_login=committer.get("login"),
    )


def classify_diff(commit: dict[str, Any]) -> DiffShape:
    """What the commit's patch moved, split into the pin and everything else.

    A file counts as a call site only if it is source and is not dependency bookkeeping, and
    only if a line in it changed that is not itself the pin. That last condition is what stops a
    lockfile bumped beside a pin -- or a source file where the pin is the only edit -- reading
    as a migration.
    """
    files = commit.get("files") or []
    changed: list[tuple[str, str]] = []
    for entry in files:
        for line in (entry.get("patch") or "").splitlines():
            if line[:3] in ("+++", "---") or line[:1] not in "+-":
                continue
            changed.append((entry.get("filename") or "", line[1:]))

    touches_pin = any(PIN_LINE.search(text) for _, text in changed)
    call_sites = {
        name
        for name, text in changed
        if text.strip()
        and not PIN_LINE.search(text)
        and SOURCE_FILE.search(name)
        and not DEPENDENCY_FILE.search(name)
    }

    return DiffShape(
        files_changed=len(files),
        touches_pin=touches_pin,
        call_site_files=tuple(sorted(call_sites)),
        changed_lines=len(changed),
    )


def read_commit_response(payload: dict[str, Any], *, repo: str, sha: str) -> CommitReading:
    """Reduce one commit response to what it says, or to a stated inability to read it.

    A payload with no `sha` is not a commit. Rate limiting, a deleted repository and a network
    fault all arrive that way, and every one of them must stay distinguishable from a commit
    that genuinely touched nothing -- which is the whole discipline `mine_stripe_migrations.py`
    was built around.
    """
    if "sha" not in payload:
        message = payload.get("message") or "no sha and no message in response"
        status = payload.get("status")
        return CommitReading(
            repo=repo,
            sha=sha,
            outcome=UNMEASURABLE,
            detail=f"{message}" + (f" (status {status})" if status else ""),
        )

    message = (payload.get("commit") or {}).get("message") or ""
    return CommitReading(
        repo=repo,
        sha=payload["sha"],
        outcome=MEASURED,
        detail="read",
        subject=message.splitlines()[0] if message else "",
        authorship=classify_authorship(payload),
        diff=classify_diff(payload),
    )


def summarise(readings: list[CommitReading]) -> dict[str, Any]:
    """Aggregate over what was read, never over what was not.

    Every proportion divides by the commits actually read. Counting an unreadable one in the
    denominator would report a smaller agent share on a worse network, which is the error the
    counting instrument's own summary exists to avoid.
    """
    read = [r for r in readings if r.outcome == MEASURED]
    unmeasurable = [r for r in readings if r.outcome == UNMEASURABLE]
    signalled = [r for r in read if r.authorship and r.authorship.any_agent_signal]
    touching = [r for r in read if r.diff and r.diff.touches_pin]

    return {
        "requested": len(readings),
        "read": len(read),
        "unmeasurable": len(unmeasurable),
        "agent_trailer": sum(1 for r in read if r.authorship and r.authorship.agent_trailer),
        "bot_identity": sum(1 for r in read if r.authorship and r.authorship.bot_identity),
        "any_agent_signal": len(signalled),
        "unsignalled": len(read) - len(signalled),
        "touching_a_pin_line": len(touching),
        "pin_only": sum(1 for r in touching if r.diff and r.diff.pin_only),
        "pin_and_call_sites": sum(1 for r in touching if r.diff and not r.diff.pin_only),
        "unsignalled_with_call_sites": sum(
            1
            for r in touching
            if r.authorship and not r.authorship.any_agent_signal
            and r.diff and not r.diff.pin_only
        ),
    }


def fetch_commit(repo: str, sha: str) -> dict[str, Any]:
    """One commit through `gh`, or whatever came out of it instead.

    A failed invocation still has to reach `read_commit_response`, so an unparseable body is
    wrapped in the shape that function reads as "could not measure". Returning an empty commit
    here would launder a network failure into a finding.

    `encoding="utf-8"` is not optional and this cohort is where it bites rather than might: the
    messages are multilingual -- Spanish, French, Slovak, Japanese in the sample this instrument
    was written for. On this machine a `text=True` subprocess decodes with cp1252, the decode
    error is raised on the reader thread where nothing can catch it, and the call returns with
    `stdout` set to `None` so the failure surfaces somewhere unrelated.
    """
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/commits/{sha}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    try:
        payload = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        return {
            "message": (result.stderr or result.stdout or "gh produced no output").strip(),
            "status": str(result.returncode),
        }
    return payload if isinstance(payload, dict) else {"message": "response was not an object"}


def search_commits(query: str, *, sort: str = "author-date", order: str = "desc") -> dict[str, Any]:
    """One commit search, sorted rather than left to relevance.

    Relevance ranking is what made the count's own sample unrepresentative, and it says so about
    itself. Sorting by author date and reading both ends is not a random sample either, but it
    is a different slice than the top of a relevance list, and taking both is cheap.
    """
    result = subprocess.run(
        [
            "gh", "api", "-X", "GET", "search/commits",
            "-f", f"q={query}", "-f", "per_page=100", "-f", f"sort={sort}", "-f", f"order={order}",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    try:
        payload = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        return {"message": (result.stderr or "gh produced no output").strip()}
    return payload if isinstance(payload, dict) else {"message": "response was not an object"}


def main() -> int:
    """Read a systematic sample of the commits naming an observed version, and report.

    Systematic rather than "the first N": the pool is collected across every observed version
    and both sort orders, deduplicated, and then every fifth commit is read. Taking the head of
    any ranking is what the count did and what it warns about in its own numbers.
    """
    from scripts.mine_stripe_migrations import OBSERVED_API_VERSIONS

    pool: list[tuple[str, str]] = []
    for version in OBSERVED_API_VERSIONS:
        for order in ("desc", "asc"):
            payload = search_commits(f'"{version}"', order=order)
            for item in payload.get("items") or []:
                repository = (item.get("repository") or {}).get("full_name")
                if repository and item.get("sha"):
                    pool.append((repository, item["sha"]))

    seen: set[tuple[str, str]] = set()
    distinct = [pair for pair in pool if not (pair in seen or seen.add(pair))]
    sample = distinct[::5]

    readings = [read_commit_response(fetch_commit(repo, sha), repo=repo, sha=sha)
                for repo, sha in sample]

    for reading in readings:
        if not reading.is_final:
            print(f"{reading.repo}@{reading.sha[:7]}: {reading.detail}")
            continue
        signals = []
        if reading.authorship and reading.authorship.agent_trailer:
            signals.append("agent-trailer")
        if reading.authorship and reading.authorship.bot_identity:
            signals.append("bot-identity")
        shape = "pin-only" if reading.diff and reading.diff.pin_only else (
            "pin+call-sites" if reading.diff and reading.diff.touches_pin else "no-pin-line"
        )
        print(f"{reading.repo}@{reading.sha[:7]}  {shape:<14} {'+'.join(signals) or 'unsignalled':<26} "
              f"{reading.subject[:52]}")

    print(f"\npool: {len(pool)} hits, {len(distinct)} distinct, {len(sample)} sampled")
    print(json.dumps(summarise(readings), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
