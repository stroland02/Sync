"""The counting half of the ground-truth measurement, driven from committed fixtures.

No test here invokes `gh` or touches the network. GitHub's search API is a vendor
API, and the repository's rule against calling one from a test is what forces the
split the script is built around: fetching is impure and untested, counting is
pure and is all that is asserted on.
"""

import json
from pathlib import Path

from scripts.mine_stripe_migrations import (
    MEASURED,
    TRUNCATED,
    UNMEASURABLE,
    count_search_response,
    summarise,
)

FIXTURES = Path(__file__).parent / "fixtures" / "github_search"


def _payload(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def test_a_normal_response_reports_the_total_the_api_states():
    """`total_count` is the number the spec asks for, not the length of the page.

    The page is capped well below the total, so counting `items` would answer a
    question nobody asked and would look like a plausible total.
    """
    count = count_search_response(_payload("code_pins_page"), query="q")
    assert count.outcome == MEASURED
    assert count.total == 2128
    assert count.total != len(_payload("code_pins_page")["items"])


def test_repositories_in_the_page_are_counted_distinctly_and_scoped_to_the_page():
    """Code search counts files; the spec's question is about repositories.

    Three files across two repositories is two repositories, and that ratio is
    only observable for the page actually returned -- never for the total.
    """
    count = count_search_response(_payload("code_pins_page"), query="q")
    assert count.repositories_in_page == 2
    assert count.files_in_page == 3


def test_a_truncated_response_is_not_presented_as_a_final_number():
    """`incomplete_results` means the API gave up mid-search.

    The total is still worth recording, but a caller that cannot tell it apart
    from a settled one will quote it as fact.
    """
    count = count_search_response(_payload("code_pins_incomplete"), query="q")
    assert count.outcome == TRUNCATED
    assert count.total == 4991
    assert not count.is_final


def test_a_rate_limited_response_could_not_measure_rather_than_measured_zero():
    """The distinction the whole count depends on.

    Zero repositories pin a Stripe API version is a finding that kills the
    approach. Failing to ask the question is not a finding at all. A counter
    that answers 0 for both makes those two indistinguishable in the report.
    """
    count = count_search_response(_payload("search_rate_limited"), query="q")
    assert count.outcome == UNMEASURABLE
    assert count.total is None
    assert "rate limit" in count.detail.lower()


def test_a_genuinely_empty_result_is_measured_zero_and_not_confused_with_failure():
    """The other side of the same distinction, which is why both fixtures exist."""
    count = count_search_response(_payload("search_empty"), query="q")
    assert count.outcome == MEASURED
    assert count.total == 0
    assert count.is_final


def test_the_two_zero_shaped_answers_do_not_compare_equal():
    """Stated directly, because every other assertion here could pass while this fails."""
    failed = count_search_response(_payload("search_rate_limited"), query="q")
    empty = count_search_response(_payload("search_empty"), query="q")
    assert failed.total != empty.total
    assert failed.outcome != empty.outcome


def test_the_query_is_carried_alongside_its_number():
    """A count with no query beside it cannot be reproduced or challenged."""
    count = count_search_response(_payload("code_pins_page"), query='"apiVersion" language:typescript')
    assert count.query == '"apiVersion" language:typescript'


def test_the_summary_separates_what_was_measured_from_what_could_not_be():
    """A summary that totals across failures reports a number it does not have."""
    counts = [
        count_search_response(_payload("code_pins_page"), query="a"),
        count_search_response(_payload("code_pins_incomplete"), query="b"),
        count_search_response(_payload("search_rate_limited"), query="c"),
        count_search_response(_payload("search_empty"), query="d"),
    ]
    summary = summarise(counts)
    assert summary["measured"] == 2
    assert summary["truncated"] == 1
    assert summary["unmeasurable"] == 1
    assert summary["queries_run"] == 4
    assert "c" in summary["unmeasurable_queries"]


def test_the_summary_refuses_to_add_up_totals_it_does_not_have():
    """The sum spans settled queries only, and says what it left out.

    A truncated query carries a real number, which is exactly why it is the one
    that can slip into a total unnoticed: 2128 and 7119 are both plausible, and
    only one of them is a figure the API settled on.
    """
    counts = [
        count_search_response(_payload("code_pins_page"), query="a"),
        count_search_response(_payload("code_pins_incomplete"), query="b"),
        count_search_response(_payload("search_rate_limited"), query="c"),
    ]
    summary = summarise(counts)
    assert summary["total_over_final_queries"] == 2128
    assert summary["truncated_queries"] == ["b"]
    assert summary["unmeasurable"] == 1
