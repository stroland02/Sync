"""A third vendor, and what it proves the first two had taught the parser.

`parse_deprecation_table` was written against two pages that agree on more than they had any
right to: both publish pipe tables, both name models with a bare identifier, and both put the
date in a cell. None of that is a fact about vendor deprecation pages -- it is a fact about
those two pages, and this file is where the difference is measured.

Cloudflare publishes Workers AI model deprecations as a bulleted list under a heading that
carries the date, and names models with a namespaced path (`@cf/meta/llama-3.1-8b-instruct`).
Both are ordinary Markdown and neither was readable.

The fixture is the real page, captured once by hand on 2026-07-29 from
`https://developers.cloudflare.com/changelog/post/2026-05-08-planned-model-deprecations/index.md`
(4159 bytes, sha256 c2cb3e804cf4befd5f7fd683f2a5ec18144e27ba054a638da7c8fa1df2f68013 as
served). No test fetches it.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

import pytest

from sync.signals.deprecations import (
    CLOUDFLARE,
    ModelDeprecation,
    parse_deprecation_table,
    to_vendor_changes,
)

FIXTURES = Path(__file__).parent / "fixtures" / "deprecations"

# After the page's stated deprecation date of May 30, 2026, which is what makes these rows
# retired rather than deprecated. Pinned so the assertions do not change meaning with the clock.
TODAY = date(2026, 7, 29)


def _page(name: str) -> str:
    return (FIXTURES / f"{name}.md").read_text(encoding="utf-8")


def _rows(name: str, vendor: str) -> dict[str, ModelDeprecation]:
    return {
        row.model_id: row
        for row in parse_deprecation_table(vendor, _page(name), today=TODAY)
    }


@pytest.fixture(scope="module")
def cloudflare() -> dict[str, ModelDeprecation]:
    return _rows("cloudflare-workers-ai", "cloudflare")


# --- the page parses to the rows it actually lists ---------------------------------

# Verbatim from the "Models deprecated on May 30, 2026" list, in the order the page writes them.
DEPRECATED = (
    "@cf/moonshotai/kimi-k2.5",
    "@hf/meta-llama/meta-llama-3-8b-instruct",
    "@cf/meta/llama-3-8b-instruct",
    "@cf/meta/llama-3-8b-instruct-awq",
    "@cf/meta/llama-3.1-8b-instruct",
    "@cf/meta/llama-3.1-8b-instruct-awq",
    "@cf/meta/llama-3.1-70b-instruct",
    "@cf/meta/llama-2-7b-chat-int8",
    "@cf/meta/llama-2-7b-chat-fp16",
    "@cf/mistral/mistral-7b-instruct-v0.1",
    "@hf/mistral/mistral-7b-instruct-v0.2",
    "@hf/google/gemma-7b-it",
    "@cf/google/gemma-3-12b-it",
    "@hf/nousresearch/hermes-2-pro-mistral-7b",
    "@cf/microsoft/phi-2",
    "@cf/defog/sqlcoder-7b-2",
    "@cf/unum/uform-gen2-qwen-500m",
    "@cf/facebook/bart-large-cnn",
)


def test_the_published_page_parses_to_the_models_it_lists(cloudflare):
    """Eighteen, which is the count the page's own summary states."""
    assert set(cloudflare) == set(DEPRECATED)
    assert len(cloudflare) == 18


def test_a_namespaced_model_id_survives_intact(cloudflare):
    """`@cf/meta/llama-3.1-8b-instruct` is the string a customer writes, slashes and all.

    The literal indexer matches on the value, so anything trimmed here is a model that is
    never found in source.
    """
    assert cloudflare["@cf/meta/llama-3.1-8b-instruct"].model_id == "@cf/meta/llama-3.1-8b-instruct"


def test_the_retirement_date_comes_from_the_section_heading(cloudflare):
    """No cell carries it. "Models deprecated on May 30, 2026" is the only place it appears.

    Indexed by the expected ids rather than iterated over whatever parsed, so a parser that
    returns nothing fails here instead of satisfying the assertion over an empty set.
    """
    assert {cloudflare[model].retirement_date for model in DEPRECATED} == {date(2026, 5, 30)}


def test_the_state_is_derived_from_that_date(cloudflare):
    """Past the date, so retired -- the same derivation the second vendor already needed."""
    assert {cloudflare[model].state for model in DEPRECATED} == {"retired"}


def test_the_derived_state_moves_with_the_clock():
    before = _rows_at(date(2026, 1, 1))
    assert {before[model].state for model in DEPRECATED} == {"deprecated"}


def _rows_at(today: date) -> dict[str, ModelDeprecation]:
    return {
        row.model_id: row
        for row in parse_deprecation_table(
            "cloudflare", _page("cloudflare-workers-ai"), today=today
        )
    }


def test_an_arrow_names_the_replacement(cloudflare):
    """One bullet carries `--> @cf/moonshotai/kimi-k2.6`, which is the whole migration.

    Neither existing vendor writes a replacement this way; both use a third table column.
    """
    assert cloudflare["@cf/moonshotai/kimi-k2.5"].replacement == "@cf/moonshotai/kimi-k2.6"


def test_a_bullet_with_no_arrow_has_no_replacement(cloudflare):
    """Seventeen of the eighteen name no successor, and inventing one is the failure the
    placeholder rule already exists to prevent."""
    named = {model for model, row in cloudflare.items() if row.replacement is not None}
    assert named == {"@cf/moonshotai/kimi-k2.5"}


# --- the sections that must not become deprecations --------------------------------

# The page lists these under "Variants that remain active" -- immediately after the deprecated
# list and in the same bullet shape. Reading them as deprecated would put a breaking finding on
# six models the vendor just promised to keep.
STILL_ACTIVE = (
    "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
    "@cf/meta/llama-3.1-8b-instruct-fast",
    "@cf/google/gemma-7b-it-lora",
    "@cf/google/gemma-2b-it-lora",
    "@cf/mistral/mistral-7b-instruct-v0.2-lora",
    "@cf/meta-llama/llama-2-7b-chat-hf-lora",
)


@pytest.mark.parametrize("model", STILL_ACTIVE)
def test_a_model_the_page_says_remains_active_is_not_a_row(cloudflare, model: str):
    """The dated heading is what opens the list, so an undated one has to close it.

    Without that the six variants below it are read as retired, and the pipeline opens pull
    requests migrating models that are not going anywhere.
    """
    assert model not in cloudflare


@pytest.mark.parametrize(
    "model",
    ["@cf/zai-org/glm-4.7-flash", "@cf/google/gemma-4-26b-a4b-it", "@cf/moonshotai/kimi-k2.6"],
)
def test_a_recommended_replacement_is_not_itself_deprecated(cloudflare, model: str):
    """These sit in a bulleted list too, above the dated heading rather than below it."""
    assert model not in cloudflare


# --- the exclusion that must survive the new shape ---------------------------------

# An endpoint written into the shape this vendor uses. OpenAI deprecates endpoints in tables
# beside models; nothing stops a vendor doing it in a list, and the answer must not change.
ENDPOINT_IN_A_LIST = """\
#### Removed on May 30, 2026

* `/v1/edits`
* `@cf/meta/llama-3-8b-instruct`
* [/v1/models](https://platform.openai.com/docs/api-reference/models)
"""


def test_an_endpoint_path_is_still_not_a_model():
    """A leading slash is a path. A model id is namespaced and has no leading slash, which is
    what lets one rule admit `@cf/meta/...` and keep refusing `/v1/edits`."""
    rows = _by_id(parse_deprecation_table("cloudflare", ENDPOINT_IN_A_LIST, today=TODAY))
    assert "/v1/edits" not in rows


def test_a_markdown_link_in_a_list_is_still_not_a_model():
    rows = _by_id(parse_deprecation_table("cloudflare", ENDPOINT_IN_A_LIST, today=TODAY))
    assert not any("(" in model or "[" in model for model in rows)


def test_the_real_model_beside_them_still_parses():
    """The exclusion has to stay narrow, or it takes the models with it."""
    rows = _by_id(parse_deprecation_table("cloudflare", ENDPOINT_IN_A_LIST, today=TODAY))
    assert "@cf/meta/llama-3-8b-instruct" in rows


def _by_id(rows: list[ModelDeprecation]) -> dict[str, ModelDeprecation]:
    return {row.model_id: row for row in rows}


# --- one model named twice is one row ----------------------------------------------

# A vendor may extend a deadline by republishing a model under a later heading, which is
# exactly what this page's Kimi section describes in prose.
LISTED_TWICE = """\
#### Models deprecated on May 10, 2026

* `@cf/moonshotai/kimi-k2.5`

#### Models deprecated on May 30, 2026

* `@cf/moonshotai/kimi-k2.5`
"""


def test_a_model_listed_under_two_dated_headings_yields_one_row():
    """Every stage is idempotent and every table has a natural key -- one model is one row.

    Two rows for one model would double-count the finding and give the graph two retirement
    dates for one string, with nothing downstream able to say which is current.
    """
    rows = parse_deprecation_table("cloudflare", LISTED_TWICE, today=TODAY)
    assert [row.model_id for row in rows] == ["@cf/moonshotai/kimi-k2.5"]
    assert rows[0].retirement_date == date(2026, 5, 10)


# The two shapes on one page: a model announced in a table and repeated in a list.
TABLE_AND_LIST = """\
| Shutdown date | Model            | Recommended replacement |
| ------------- | ---------------- | ----------------------- |
| Mar 14, 2026  | `@cf/meta/old`   | `@cf/meta/new`          |

#### Models deprecated on May 30, 2026

* `@cf/meta/old`
"""


def test_a_table_row_is_not_repeated_by_the_list_beneath_it():
    """The table wins, because it named a replacement the list does not."""
    rows = parse_deprecation_table("cloudflare", TABLE_AND_LIST, today=TODAY)
    assert len(rows) == 1
    assert rows[0].replacement == "@cf/meta/new"
    assert rows[0].retirement_date == date(2026, 3, 14)


# --- prefixes derived from the page, never guessed ---------------------------------

# A Workers AI model id is `@<namespace>/<org>/<name>`. Deliberately not the parser's own
# notion of a model id: a prefix check that asked the parser what it found could only ever
# confirm the prefixes cover what already parsed.
_MODEL_ID = re.compile(r"@[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+")


def _every_model_id_named() -> set[str]:
    return set(_MODEL_ID.findall(_page("cloudflare-workers-ai")))


def test_the_page_names_the_ids_this_check_expects():
    """Guards the check itself. A regex that matched nothing would make the coverage
    assertion below pass over an empty set and prove nothing at all."""
    assert len(_every_model_id_named()) == 27


def test_every_model_id_the_page_names_is_covered_by_the_prefixes():
    """The `code-`/`codex-`/`ft-` defect, in this vendor's spelling.

    Guessing `@cf/` from the vendor's name misses four `@hf/` ids -- three of them among the
    eighteen actually being retired. The finding would be raised with no call site to attach
    it to, and nothing would report a fault.
    """
    uncovered = sorted(
        model for model in _every_model_id_named() if not model.startswith(CLOUDFLARE.prefixes)
    )
    assert uncovered == [], f"never indexed: {uncovered}"


def test_the_prefixes_are_not_one_family():
    """States what the check above found, so a later edit narrowing the list fails here with
    the reason rather than only in the coverage assertion."""
    assert set(CLOUDFLARE.prefixes) == {"@cf/", "@hf/"}


def test_the_third_source_is_complete():
    assert CLOUDFLARE.vendor_id == "cloudflare"
    assert CLOUDFLARE.url.startswith("https://")
    assert CLOUDFLARE.url.endswith(".md")


def test_every_change_the_vendor_produces_is_indexable(cloudflare):
    """The join the prefixes exist to serve: every emitted change must be a literal the
    indexer would have found."""
    changes = to_vendor_changes(list(cloudflare.values()), "a", "b", today=TODAY)
    assert changes
    assert all(c.operation_id.startswith(CLOUDFLARE.prefixes) for c in changes)


def test_a_retired_model_is_breaking(cloudflare):
    changes = {c.operation_id: c for c in to_vendor_changes(list(cloudflare.values()), "a", "b", today=TODAY)}
    assert changes["@cf/meta/llama-3.1-8b-instruct"].severity == "breaking"
    assert changes["@cf/moonshotai/kimi-k2.5"].raw["replacement"] == "@cf/moonshotai/kimi-k2.6"


# --- the finding has somewhere to land ---------------------------------------------

# A Workers AI call passes the model as a bare string, which is the shape the literal indexer
# exists for -- no member chain leads to it and no type names it.
WORKER = """\
const a = await env.AI.run("@cf/moonshotai/kimi-k2.5", { prompt: p });
const b = await env.AI.run("@cf/meta/llama-3.1-8b-instruct", { prompt: p });
const c = await env.AI.run("@cf/zai-org/glm-4.7-flash", { prompt: p });
"""


def test_a_path_shaped_model_id_survives_index_join_and_patch(cloudflare):
    """The whole reason the slash rule had to change, proven at the far end.

    A model id carrying separators has to reach a call site and come back out as an applied
    swap. Neither `sync.index` nor `sync.detect` was touched to make this work -- the indexer
    filters on `str.startswith` and the join is on `operation_id` equality, so a namespaced id
    was never the problem there.
    """
    from sync.index.literals import index_operation_literals
    from sync.route import apply_rules, model_literal_swap

    sites = index_operation_literals(
        WORKER, path="w.ts", repo_id="r", vendor_id="cloudflare",
        sdk_version="1", prefixes=CLOUDFLARE.prefixes,
    )
    assert {site.operation_id for site in sites} == {
        "@cf/moonshotai/kimi-k2.5",
        "@cf/meta/llama-3.1-8b-instruct",
        "@cf/zai-org/glm-4.7-flash",
    }

    changes = {c.operation_id: c for c in to_vendor_changes(list(cloudflare.values()), "a", "b", today=TODAY)}
    dying = {site.operation_id for site in sites} & set(changes)
    assert dying == {"@cf/moonshotai/kimi-k2.5", "@cf/meta/llama-3.1-8b-instruct"}

    patched = apply_rules(
        model_literal_swap(changes["@cf/moonshotai/kimi-k2.5"], language="typescript"),
        WORKER,
        "typescript",
    )

    assert "@cf/moonshotai/kimi-k2.6" in patched
    # The healthy model and the model with no published replacement are both left alone.
    assert "@cf/zai-org/glm-4.7-flash" in patched
    assert "@cf/meta/llama-3.1-8b-instruct" in patched


# --- the two existing vendors, which must not have moved ---------------------------

# Captured the same day as the third, from the URLs the shipped sources already name. Counts
# and digests were taken from the parser *before* this task changed it -- a generalization that
# alters an existing vendor's output by one row is a regression wearing better clothes.
UNCHANGED = {
    "anthropic": (29, "a8ad11d8a49bb85f1ec1ea1b4c1bdf6f680c5104cf6356d9b971a1ed77f4e9ca"),
    "openai": (108, "e0172d04f010cc10cb3716789e048e6c24be6d46a91eb8472a11a59026dde6f6"),
}


def _digest(vendor: str) -> tuple[int, str]:
    rows = parse_deprecation_table(vendor, _page(vendor), today=TODAY)
    canonical = json.dumps(
        sorted(
            [
                row.model_id,
                row.state,
                row.replacement,
                row.deprecated_date.isoformat() if row.deprecated_date else None,
                row.retirement_date.isoformat() if row.retirement_date else None,
                row.not_before.isoformat() if row.not_before else None,
            ]
            for row in rows
        ),
        sort_keys=True,
    )
    return len(rows), hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@pytest.mark.parametrize("vendor", sorted(UNCHANGED))
def test_an_existing_vendor_parses_exactly_as_it_did(vendor: str):
    """Every field of every row, not merely the count.

    A count alone would miss a replacement that stopped resolving or a date that moved, which
    are the two ways this change could damage a vendor it never mentions.
    """
    assert _digest(vendor) == UNCHANGED[vendor]


def test_the_openai_page_carries_a_byte_that_is_not_ascii():
    """The reason this fixture is worth its size.

    `CLAUDE.md` records that every fixture in this repository is ASCII, so no test can catch a
    missing `encoding="utf-8"`. This one is not: the page writes `DALL-E` with an interpunct,
    and reading it under cp1252 fails here rather than against real vendor data.
    """
    body = _page("openai")
    assert not body.isascii()
