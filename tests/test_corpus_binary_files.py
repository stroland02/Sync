"""A checkout carrying a file that is not UTF-8, which is most real repositories.

`sync.cli._score_corpus` read every file under the checkout with `read_text(encoding="utf-8")`, so
one PNG anywhere ended the run. The Stripe Connect demo carries 63 such files. That is a coverage
problem rather than an inconvenience: every candidate repository with an image, a font, a compiled
asset or a `.ico` was unscoreable, which is why the frozen corpus is four repositories.

The fix is the one `CLAUDE.md` already names -- bytes that are not text are not decoded at all --
and the shape it takes here is a skip. Not `errors="replace"`: a binary mangled into replacement
characters becomes a source file the indexer will parse, and whatever tree-sitter makes of it can
only produce phantom call sites. Not `errors="ignore"` either, for the same reason.

The count is the part that is not optional. `2026-07-27-sync-benchmark-gates.md` is explicit that
silent exclusion turns a biased sample into an unqualified number, and a skip nobody counts is how
a corpus stops describing the repository it names. The paths are carried too, because the one case
this cannot tell apart from a binary is a source file in a legacy encoding, and a reader who can
see `src/legacy.ts` in the list can act on it where a reader handed only `64` cannot.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from scripts.fetch_corpus_repositories import materialise as materialise_checkout
from scripts.score_corpus import PairResult, aggregate, render
from sync.benchmark.binding import BindingLabel, EmittedFinding
from sync.benchmark.checkout import read_checkout
from sync.benchmark.report import render_report
from sync.benchmark.score import SYNTHETIC_REFERENCE
from sync.cli import _score_corpus

# Invalid UTF-8 by construction: 0xFF and 0xFE are not legal lead bytes in any position.
PNG_BYTES = b"\x89PNG\r\n\x1a\n\xff\xd8\xff\xe0\x00\x10JFIF"

# cp1252 for "resume" with two accented characters. Decodes cleanly as cp1252 and raises as UTF-8,
# which is exactly the case that cannot be told from a binary without guessing.
LEGACY_BYTES = "résumé".encode("cp1252")

SPEC_JSON = json.dumps({"openapi": "3.0.0", "info": {"title": "t", "version": "1"}, "paths": {}})

BILLING_TS = """import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function chargeCustomer(amount: number) {
  const charge = await stripe.charges.create({ amount, currency: 'eur' });
  return charge.id;
}
"""


def _checkout(tmp_path: Path) -> Path:
    """A minimal TypeScript repository the indexer recognises, with no binary in it yet."""
    checkout = tmp_path / "checkout"
    (checkout / "src").mkdir(parents=True)
    (checkout / "package.json").write_text(
        json.dumps({"dependencies": {"stripe": "^18.0.0"}}), encoding="utf-8"
    )
    (checkout / "src" / "billing.ts").write_text(BILLING_TS, encoding="utf-8")
    return checkout


# --- reading a checkout ------------------------------------------------------------


def test_a_file_that_is_not_utf_8_is_skipped_rather_than_ending_the_run(tmp_path):
    """One PNG made a repository unscoreable. Nothing downstream of this mapping wants a PNG's
    bytes -- the indexers only ever read source -- so the file has no business being decoded."""
    checkout = _checkout(tmp_path)
    (checkout / "assets").mkdir()
    (checkout / "assets" / "logo.png").write_bytes(PNG_BYTES)

    sources, skipped = read_checkout(checkout)

    assert "src/billing.ts" in sources
    assert "assets/logo.png" not in sources
    assert skipped == ["assets/logo.png"]


def test_a_skipped_file_is_named_and_not_merely_counted(tmp_path):
    """The one case a decode failure cannot distinguish is a source file in a legacy encoding, and
    that skip loses real call sites. A count says sixty-four; a path says which sixty-four, and a
    `.ts` among them is visible to a reader who could not otherwise have known to look."""
    checkout = _checkout(tmp_path)
    (checkout / "src" / "legacy.ts").write_bytes(LEGACY_BYTES)
    (checkout / "logo.png").write_bytes(PNG_BYTES)

    _, skipped = read_checkout(checkout)

    assert skipped == ["logo.png", "src/legacy.ts"]


def test_a_utf_8_file_with_non_ascii_bytes_is_not_skipped(tmp_path):
    """The skip has to be a decode failure and nothing coarser. A source file carrying an accented
    identifier or a currency symbol is ordinary text, and skipping it would drop real call sites
    for the reason `CLAUDE.md` says no test in this repository would ever catch."""
    checkout = _checkout(tmp_path)
    (checkout / "src" / "prices.ts").write_text("export const label = '12,50 €';\n",
                                                encoding="utf-8")

    sources, skipped = read_checkout(checkout)

    assert skipped == []
    assert "€" in sources["src/prices.ts"]


def test_line_endings_are_normalised_exactly_as_they_were_before(tmp_path):
    """`read_text` translates newlines and the mapping this feeds is what call site positions and
    content hashes are computed from. A skip that also changed decoding semantics would move the
    corpus score for a reason that has nothing to do with binaries."""
    checkout = _checkout(tmp_path)
    (checkout / "src" / "crlf.ts").write_bytes(b"const a = 1;\r\nconst b = 2;\r\n")

    sources, _ = read_checkout(checkout)

    assert sources["src/crlf.ts"] == "const a = 1;\nconst b = 2;\n"


def test_an_install_and_the_git_directory_are_still_not_read(tmp_path):
    """Unchanged, and asserted because the walk moved. `node_modules` is an install rather than
    source and `.git` is bookkeeping; reading either would put tens of thousands of files through
    the indexer and index the vendor's own SDK as though the customer had written it."""
    checkout = _checkout(tmp_path)
    (checkout / "node_modules" / "stripe").mkdir(parents=True)
    (checkout / "node_modules" / "stripe" / "index.js").write_text("x", encoding="utf-8")
    (checkout / ".git").mkdir()
    (checkout / ".git" / "index").write_bytes(PNG_BYTES)

    sources, skipped = read_checkout(checkout)

    assert list(sources) == ["package.json", "src/billing.ts"]
    assert skipped == []


# --- what the score carries and reports ---------------------------------------------


@pytest.fixture()
def corpus(tmp_path: Path) -> Path:
    """A pair specification whose checkout carries two files the scorer cannot read."""
    checkout = _checkout(tmp_path)
    (checkout / "assets").mkdir()
    (checkout / "assets" / "logo.png").write_bytes(PNG_BYTES)
    (checkout / "favicon.ico").write_bytes(PNG_BYTES)

    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "symbols.json").write_text(
        json.dumps({
            "stripe.charges.create": {
                "operation_id": "PostCharges", "http_method": "post", "path": "/v1/charges"
            },
        }),
        encoding="utf-8",
    )
    for version in ("2026-05-01", "2026-11-01"):
        (cache / f"{version}.json").write_text(SPEC_JSON, encoding="utf-8")

    spec = tmp_path / "corpus.yaml"
    spec.write_text(
        yaml.safe_dump({
            "repo": str(checkout),
            "vendor": "stripe",
            "cache": str(cache),
            "from_version": "2026-05-01",
            "to_version": "2026-11-01",
            "change": {
                "kind": "request-property-removed",
                "operation": "PostCharges",
                "field": "receipt_email",
            },
        }),
        encoding="utf-8",
    )
    return spec


@pytest.fixture()
def score_dsn() -> str:
    """A database of its own, because scoring truncates the graph it scores in."""
    import os

    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    dsn = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")
    parts = conninfo_to_dict(dsn)
    name = f"{parts['dbname']}_binary"
    admin = make_conninfo(**{**parts, "dbname": "postgres"})
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    return make_conninfo(**{**parts, "dbname": name})


def test_a_repository_with_a_binary_in_it_scores_and_says_what_it_could_not_read(
    corpus, score_dsn
):
    """The whole task, end to end. A checkout with a PNG and an icon in it used to raise
    `UnicodeDecodeError` before a single call site was indexed; it scores now, and the result
    carries the two paths so the number beside it can be read as covering the tree it names."""
    scored = _score_corpus(corpus, score_dsn)

    assert scored.affected_sites == 1
    assert scored.skipped_files == ("assets/logo.png", "favicon.ico")


# --- what the two reports say about it ------------------------------------------------


def _pair(name: str, skipped=()) -> PairResult:
    # Call site ids are per repository and these pool into one label set, so each pair carries
    # its own; a repeated (call site, change) pair is refused by the scorer and rightly.
    site = f"{name}-site"
    return PairResult(
        name=name, scored=True,
        findings=[EmittedFinding(call_site_id=site, vendor_change_id="c", binding_rung="static")],
        labels=[BindingLabel(call_site_id=site, vendor_change_id="c", affected=True,
                             rung="static")],
        affected_sites=1, unaffected_sites=0, skipped_files=tuple(skipped),
    )


def test_the_corpus_pools_skipped_paths_without_counting_one_repository_twice():
    """Four specifications name `furever`, and its 63 images are the same 63 images in each. A
    pooled sum would report 252 skipped paths over a corpus that has 63, which is the kind of
    number that reads as a much bigger problem than the one it describes."""
    score = aggregate([
        _pair("furever-a", ("public/logo.png", "public/hero.jpg")),
        _pair("furever-b", ("public/logo.png", "public/hero.jpg")),
    ])

    assert score.skipped_files == ["public/hero.jpg", "public/logo.png"]


def test_the_rendered_corpus_score_names_every_path_it_could_not_read():
    """Counted in the summary and named at the bottom. The count is what stops the exclusion
    being silent; the names are what let a reader notice a `.ts` among the images, which is the
    only case where real call sites went missing."""
    rendered = render(aggregate([_pair("a", ("public/logo.png", "src/legacy.ts"))]),
                      reference=SYNTHETIC_REFERENCE)

    assert "paths not read        2" in rendered
    assert "Checkout paths not read as source" in rendered
    assert "  src/legacy.ts" in rendered


def test_a_corpus_that_read_every_file_prints_no_such_heading():
    """A heading that appears on every run is a heading the next reader learns to skip, and this
    one has to be noticed on the run where it appears."""
    rendered = render(aggregate([_pair("a")]), reference=SYNTHETIC_REFERENCE)

    assert "paths not read        0" in rendered
    assert "Checkout paths not read as source" not in rendered


def test_the_single_pair_report_says_what_it_could_not_read_too():
    """`sync benchmark --score-pair` prints a score, so it prints this. A command that scored one
    repository and said nothing about the 63 files it walked past would be the silent exclusion
    with a different surface."""
    rendered = render_report([], skipped_files=("public/logo.png",))

    assert "Checkout paths not read as source (1)" in rendered
    assert "  public/logo.png" in rendered


# --- the fetcher materialises the tree it was pinned to -------------------------------


def test_the_fetcher_copies_a_file_it_cannot_decode_rather_than_dropping_it(tmp_path):
    """Two components deciding what counts as source is one too many, and the fetcher's copy is
    the one that made the corpus score a modified tree. `_score_corpus` skips what it cannot read,
    so the fetch has no reason to pre-filter and every reason not to: the tree digest is worth
    more pinning what the vendor published than what a filter left behind."""
    source = tmp_path / "src"
    (source / "app").mkdir(parents=True)
    (source / "app" / "page.ts").write_text("const a = 1;\n", encoding="utf-8")
    (source / "app" / "logo.png").write_bytes(PNG_BYTES)

    written = materialise_checkout(source, tmp_path / "out")

    assert written == 2
    assert (tmp_path / "out" / "app" / "logo.png").read_bytes() == PNG_BYTES


def test_the_fetcher_copies_bytes_verbatim_so_the_digest_is_over_what_was_published(tmp_path):
    """A checkout carrying CRLF has to stay byte-identical to what was fetched. Decoding and
    re-encoding was already avoided for that reason; copying the bytes makes it structural rather
    than careful."""
    source = tmp_path / "src"
    source.mkdir()
    (source / "crlf.ts").write_bytes(b"const a = 1;\r\n")

    materialise_checkout(source, tmp_path / "out")

    assert (tmp_path / "out" / "crlf.ts").read_bytes() == b"const a = 1;\r\n"


def test_what_the_fetcher_materialises_is_exactly_what_the_scorer_walks(tmp_path):
    """The tree digest is over what the fetch produced and the score is over what the scorer read.
    If those two walks ever disagree the digest pins one set of files while the number is taken
    over another, and nothing in either component would notice -- so they share `tree_files` and
    this is the assertion that they still do."""
    source = tmp_path / "src"
    (source / "app").mkdir(parents=True)
    (source / "node_modules").mkdir()
    (source / "app" / "page.ts").write_text("const a = 1;\n", encoding="utf-8")
    (source / "app" / "logo.png").write_bytes(PNG_BYTES)
    (source / "node_modules" / "a.js").write_text("x", encoding="utf-8")

    destination = tmp_path / "out"
    materialise_checkout(source, destination)
    sources, skipped = read_checkout(destination)

    materialised = {p.relative_to(destination).as_posix()
                    for p in destination.rglob("*") if p.is_file()}
    assert materialised == set(sources) | set(skipped)


def test_the_fetcher_still_materialises_neither_an_install_nor_the_git_directory(tmp_path):
    """Copying them would mean tens of thousands of files written to be ignored, and a tree digest
    over an install rather than over a repository."""
    source = tmp_path / "src"
    (source / "node_modules").mkdir(parents=True)
    (source / ".git").mkdir()
    (source / "node_modules" / "a.js").write_text("x", encoding="utf-8")
    (source / ".git" / "HEAD").write_text("ref\n", encoding="utf-8")
    (source / "index.ts").write_text("const a = 1;\n", encoding="utf-8")

    written = materialise_checkout(source, tmp_path / "out")

    assert written == 1
    assert not (tmp_path / "out" / "node_modules").exists()
    assert not (tmp_path / "out" / ".git").exists()
