"""Count the ground truth available for mining, before anyone builds a harness to mine it.

`docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md` proposes labelling binding
precision and recall from migrations that already happened: a repository pins a Stripe
API version, later bumps it across a breaking release, and the human's own commit is the
correct answer. The spec is emphatic that the first deliverable is the count, not the
harness, because a handful of repositories kills the approach on sample size.

This is the instrument for that count and nothing more. It clones nothing, checks out
nothing, and runs no part of Sync's pipeline.

The split between fetching and counting is the design. Fetching shells out to `gh` and
touches the network, so no test may drive it. Counting takes parsed JSON and returns a
structure, which is why the numbers this produces are testable at all.

The distinction the whole exercise rests on is between *measured zero* and *could not
measure*. Zero repositories pinning a Stripe API version is a finding that ends the
approach; a rate-limited query is not a finding at all. A counter that answers `0` to
both hides the difference in a number that looks settled.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any

MEASURED = "measured"
TRUNCATED = "truncated"
UNMEASURABLE = "unmeasurable"


@dataclass(frozen=True)
class SearchCount:
    """One query's answer, carrying enough context to be reproduced or challenged."""

    query: str
    outcome: str
    total: int | None
    detail: str
    files_in_page: int = 0
    repositories_in_page: int | None = None

    @property
    def is_final(self) -> bool:
        """Whether this number may be quoted without a qualification beside it."""
        return self.outcome == MEASURED


def count_search_response(payload: dict[str, Any], *, query: str) -> SearchCount:
    """Reduce one GitHub search response to a number, or to a stated inability to get one.

    `total_count` is the answer, never `len(items)`: the API pages far below the total
    and a page length would look like a plausible count while answering a different
    question. The page is still worth reporting for its repository-to-file ratio, which
    is the only place that ratio is observable -- code search counts files, and the
    spec's question is about repositories.
    """
    if "total_count" not in payload:
        message = payload.get("message") or "no total_count and no message in response"
        status = payload.get("status")
        return SearchCount(
            query=query,
            outcome=UNMEASURABLE,
            total=None,
            detail=f"{message}" + (f" (status {status})" if status else ""),
        )

    items = payload.get("items") or []
    repositories = {
        item["repository"]["full_name"]
        for item in items
        if isinstance(item.get("repository"), dict) and item["repository"].get("full_name")
    }
    truncated = bool(payload.get("incomplete_results"))
    return SearchCount(
        query=query,
        outcome=TRUNCATED if truncated else MEASURED,
        total=int(payload["total_count"]),
        detail=(
            "GitHub reported incomplete_results; the search timed out and the total is a "
            "lower bound rather than a settled figure"
            if truncated
            else "complete"
        ),
        files_in_page=len(items),
        repositories_in_page=len(repositories),
    )


def summarise(counts: list[SearchCount]) -> dict[str, Any]:
    """Aggregate without adding up numbers that were never obtained.

    Totalling across a failed query silently substitutes zero for the thing that was not
    measured, which is the error this whole module exists to avoid. The sum therefore
    spans settled queries only, and the count of what it excluded travels with it.
    """
    measured = [c for c in counts if c.outcome == MEASURED]
    truncated = [c for c in counts if c.outcome == TRUNCATED]
    unmeasurable = [c for c in counts if c.outcome == UNMEASURABLE]
    return {
        "queries_run": len(counts),
        "measured": len(measured),
        "truncated": len(truncated),
        "unmeasurable": len(unmeasurable),
        "total_over_final_queries": sum(c.total or 0 for c in measured),
        "unmeasurable_queries": [c.query for c in unmeasurable],
        "truncated_queries": [c.query for c in truncated],
    }


def run_search(endpoint: str, query: str) -> dict[str, Any]:
    """Issue one search through `gh` and hand back whatever JSON came out of it.

    A failed invocation still has to reach `count_search_response`, so an unparseable
    body is wrapped in the shape that function reads as "could not measure". Returning
    an empty result here instead would launder a network failure into a finding.

    `encoding="utf-8"` is not optional: on this machine a `text=True` subprocess decodes
    with cp1252, and a decode error is raised on the reader thread where nothing can
    catch it -- the call returns with `stdout` set to `None` and the failure surfaces as
    a `TypeError` somewhere unrelated.
    """
    result = subprocess.run(
        ["gh", "api", "-X", "GET", endpoint, "-f", f"q={query}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "message": (result.stderr or result.stdout or "gh produced no output").strip(),
            "status": str(result.returncode),
        }
    return payload if isinstance(payload, dict) else {"message": "response was not an object"}


# Stripe pins its API version as an `apiVersion` assignment in the SDK constructor, and
# as `api_version` in the Python and Ruby SDKs. Each query is narrow enough to be quoted
# in the report verbatim; a broad one that cannot be reproduced is not evidence.
PIN_QUERIES = [
    ("typescript pins", "search/code", '"apiVersion: \'20" language:typescript'),
    ("javascript pins", "search/code", '"apiVersion: \'20" language:javascript'),
    ("python pins", "search/code", '"stripe.api_version" language:python'),
    ("ruby pins", "search/code", '"Stripe.api_version" language:ruby'),
]

BUMP_QUERIES = [
    ("commits naming apiVersion and stripe", "search/commits", "apiVersion stripe"),
    ("commits naming a stripe api version bump", "search/commits", "stripe api version bump"),
]

# The dated versions below are the only ones this repository can observe. No committed
# fixture carries a real Stripe release date -- `tests/fixtures/specs/charges_base.json`
# declares `"version": "base"` and `stripe_v2330_shape.json` has no `info` block at all --
# so these were read out of the `info.version` field of the specs in the gitignored
# `.cache/specs/`. That cache is not part of the repository, which means this list is not
# reproducible from a fresh clone, and it is emphatically not Stripe's own classification
# of which releases are breaking. It is three points that happen to be visible from here.
OBSERVED_API_VERSIONS = ("2026-02-25.clover", "2026-05-27.dahlia", "2026-06-24.dahlia")

BREAKING_BUMP_QUERIES = [
    (f"commits naming {version}", "search/commits", f'"{version}"')
    for version in OBSERVED_API_VERSIONS
]


def main() -> int:
    counts: list[SearchCount] = []
    for label, endpoint, query in [*PIN_QUERIES, *BUMP_QUERIES, *BREAKING_BUMP_QUERIES]:
        count = count_search_response(run_search(endpoint, query), query=query)
        counts.append(count)
        total = "could not measure" if count.total is None else count.total
        print(f"{label}\n  endpoint: {endpoint}\n  q: {query}\n  total: {total}")
        print(f"  outcome: {count.outcome} ({count.detail})")
        if count.repositories_in_page is not None:
            print(f"  page: {count.files_in_page} files across {count.repositories_in_page} repositories")
    print("\nsummary:")
    print(json.dumps(summarise(counts), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
