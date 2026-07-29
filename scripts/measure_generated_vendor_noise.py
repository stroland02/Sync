"""What rule ids the four generated-SDK vendors' own specification pairs produce.

`docs/superpowers/reports/2026-07-29-oasdiff-determinism.md` §4 measured 792,552 records and found
93% of them were `response-property-enum-value-added` -- the one kind
`sync.signals.stripe.adapter.NOISE_KINDS` drops. Every one of those records came from the Stripe
`v2320 -> v2330` pair. The same report noted that `sync.signals.generated.adapter` applies no
filter at all, and the obvious repair is to copy Stripe's constant across.

That repair would be importing a measurement from a different corpus and calling it a rule. Nobody
had measured what `anthropic`, `openai`, `cloudflare` and `vercel` produce over their *own*
specification pairs, and `CLAUDE.md` is explicit that a judgement about one vendor's release habits
belongs to that vendor. This is the missing measurement.

Where the two sides of each pair come from
------------------------------------------
A generated SDK's manifest names the specification the generator worked from, so two commits of
that manifest name two specifications, and the diff between them is the change the adapter would
report for that version pair. Stainless publishes an `openapi_spec_url` for each; Speakeasy's
`vercel/sdk` names a live URL (`https://openapi.vercel.sh/`) and *also* commits the resolved
document as `vercel-spec.json`, so the committed blob at two commits is the pinnable pair.

**That difference matters and is not cosmetic.** Between two SDK refs the adapter fetches Vercel's
live URL twice, moments apart, and diffs the current document against itself. What is measured here
is the pair Vercel's specification actually moved through, which is an upper bound on what the
adapter would find rather than what it finds today.

Every document is pinned by the sha256 of its bytes and verified before oasdiff sees it, for the
reason `scripts/fetch_measurement_inputs.py` gives: a substituted or truncated input parses,
measures, and produces a number that differs from the documented one by an amount nobody can see.
The stainless URL embeds a hash that is *not* the content hash -- two differently-named anthropic
URLs serve byte-identical documents -- so the name is not a pin and the sha256 is.

How many runs
-------------
oasdiff returns a different answer on every run over identical bytes, so a single run is a lower
bound rather than a measurement. `2026-07-29-oasdiff-convergence.md` measured the shape of that on
Stripe: the operation-level union converged on run 1 and did not move across 23 further runs, while
the natural-key union never converged. A rule id is a component of the operation-level key, so the
union of rule ids converges no later than the union of operation-level rows -- which is why this
prints the curve rather than asserting a number. Read N off the `new kinds` column.

    uv run python scripts/measure_generated_vendor_noise.py --runs 12
    uv run python scripts/measure_generated_vendor_noise.py --runs 12 --vendor anthropic

This fetches from GitHub and from the generators' spec hosts. It is a script rather than a test for
exactly that reason.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sync.signals.generated.manifest import parse_manifest  # noqa: E402

CACHE = Path(".cache/generated-specs")
BINARY = Path("tools/oasdiff.exe")

# The kind `sync.signals.stripe.adapter.NOISE_KINDS` drops, and the one this measurement exists to
# decide about for a different set of vendors. Named here rather than imported: importing one
# vendor's judgement to test whether it holds for another would make the comparison circular.
CANDIDATE = "response-property-enum-value-added"


@dataclass(frozen=True)
class SpecVersion:
    """One side of a diff: an SDK commit, and the specification that commit was generated from.

    A commit is immutable, which is what makes the pair reproducible; the sha256 is what makes it
    verifiable, since neither the manifest's `openapi_spec_hash` nor the hash embedded in the
    stainless URL is a hash of the bytes served.
    """

    repo: str
    ref: str
    sha256: str
    filename: str
    manifest: str | None = None
    """A generator manifest to resolve the specification URL out of, for a vendor that publishes
    one. `parse_manifest` reads it, so this measurement rides the same parser a run does."""
    blob_path: str | None = None
    """Or a path in the SDK repository holding the resolved specification itself."""

    @property
    def path(self) -> Path:
        return CACHE / self.filename


@dataclass(frozen=True)
class Pair:
    vendor_id: str
    label: str
    base: SpecVersion
    head: SpecVersion


def _stainless(repo: str, ref: str, sha256: str, filename: str) -> SpecVersion:
    return SpecVersion(repo=repo, ref=ref, sha256=sha256, filename=filename, manifest=".stats.yml")


ANTHROPIC = "anthropics/anthropic-sdk-python"
OPENAI = "openai/openai-python"
VERCEL = "vercel/sdk"

PAIRS: tuple[Pair, ...] = (
    # A month-wide window for each vendor, chosen to sit alongside Stripe's `v2320 -> v2330`
    # (2026-05-27 -> 2026-06-24), and an adjacent-release window, so the answer is not a fact
    # about one hop. Every adjacent window below is one whose `openapi_spec_hash` actually moved:
    # anthropic's 07-24 and 07-28 manifests carry the same hash over byte-identical documents, so
    # the adapter would skip that pair before fetching anything and measuring it would measure
    # nothing.
    Pair(
        "anthropic", "2026-06-30 -> 2026-07-28",
        _stainless(ANTHROPIC, "ab10964f48c54c691e96f29f03dd7c600452c817",
                   "7caa9a75ddbc8f19a11f63e41ec38d8d8af6499adf4429aa6cf32b1294677050",
                   "anthropic-04d07a5a32685ff9769f89d63e4ceaa49738b4d8dac73041bc9a691759350108.yml"),
        _stainless(ANTHROPIC, "36863a0d47d227f6c904cab3d3d1e7543b1e50ea",
                   "a97790bd7f185213830f19daf7392c9c1390be8811d507417398a0bf519e20f5",
                   "anthropic-6d5c96a475b06ff067a4491fc2258181f0426af6c64bcfd4be5d167a8c0d9d16.yml"),
    ),
    Pair(
        "anthropic", "2026-07-23 -> 2026-07-24",
        _stainless(ANTHROPIC, "691471837f19dd4ce50fd96eaf91993a0eb4d72a",
                   "d7893c708340adbe5971007c89503cb894307de79fe3f6325b9959dbcf3e9009",
                   "anthropic-a30621b2b3d2b09193f23ec007d16c86545991416826b7637ad7b9e5488fbf68.yml"),
        _stainless(ANTHROPIC, "70c0a64581e74d895afb49ec2ffdf4b7a4f220cf",
                   "a97790bd7f185213830f19daf7392c9c1390be8811d507417398a0bf519e20f5",
                   "anthropic-f89e311096c42998ada5ab5580a2a3b0519265f1c005af625be7a0d11ad49d3c.yml"),
    ),
    Pair(
        "openai", "2026-06-17 -> 2026-07-28",
        _stainless(OPENAI, "4d354538e8c2618e228c80f1fdc332ee1f70d1f2",
                   "827fa3e74ce9736c989f406d9f55ad8bee52c9396db5c70629a3d742ff00df84",
                   "openai-b5b621065906a2579dc180db1236ee3b08a4fca9539accc2fbbf88da0ca3923f.yml"),
        _stainless(OPENAI, "59ed1dccac26e7e92f5b91dd106dd273bf32b922",
                   "c7549184dd9540e516f912aab8ce176be232c08cc7b1ee8922c82e65517400d9",
                   "openai-9152683f2fa71f5555cbbb53123ec013b7c83ee6fed4333e76c22a6f48a05f1c.yml"),
    ),
    Pair(
        "openai", "2026-07-23 -> 2026-07-28",
        _stainless(OPENAI, "cbd2fba7c48b6376e80775cb191e2eda1d476c61",
                   "0514a733c82d272c2c7c0aae8b4ed3619c23d4ce0659206431e34cce1781f5b8",
                   "openai-0650ebae454b4200491980d7663cb7ceabcff90dcb3ed9f67c3bca3e861a2bf6.yml"),
        _stainless(OPENAI, "59ed1dccac26e7e92f5b91dd106dd273bf32b922",
                   "c7549184dd9540e516f912aab8ce176be232c08cc7b1ee8922c82e65517400d9",
                   "openai-9152683f2fa71f5555cbbb53123ec013b7c83ee6fed4333e76c22a6f48a05f1c.yml"),
    ),
    Pair(
        "vercel", "2026-06-18 -> 2026-07-28",
        SpecVersion(VERCEL, "d94d9852984d0dfcbedea86ae374827a1aa38fe5",
                    "c46f83e1ba48ddf5bc1ce7f48b8cda2086e9d8309992b1472c2da0d8cf5404fa",
                    "vercel-d94d9852984d.json", blob_path="vercel-spec.json"),
        SpecVersion(VERCEL, "142fa1bd976e91e47468cee500342efe59162bde",
                    "1610a601ceb103779397b3e6fba11c1dbb6c7b7cb1ecde430a8f85b974b7430b",
                    "vercel-142fa1bd976e.json", blob_path="vercel-spec.json"),
    ),
    Pair(
        "vercel", "2026-07-27 -> 2026-07-28",
        SpecVersion(VERCEL, "e8b9e0fa18318828b3cb0332700dcebf3bdf7d36",
                    "09f357cfe733f15553917a3777d2465236e7ef1a369f834d585e339520cd2a2c",
                    "vercel-e8b9e0fa1831.json", blob_path="vercel-spec.json"),
        SpecVersion(VERCEL, "142fa1bd976e91e47468cee500342efe59162bde",
                    "1610a601ceb103779397b3e6fba11c1dbb6c7b7cb1ecde430a8f85b974b7430b",
                    "vercel-142fa1bd976e.json", blob_path="vercel-spec.json"),
    ),
)

# The fourth configured vendor. `cloudflare-python`'s `.stats.yml` publishes an endpoint count and
# no specification URL, so `SpecSource.is_fetchable` is False and `fetch_changes` returns before
# oasdiff is invoked. There is no pair to measure, and its record count is structurally zero rather
# than measured as zero. Checked against the live manifest rather than asserted, because the day it
# starts publishing a URL is the day this vendor acquires an exposure nobody re-measured.
NOT_FETCHABLE = ("cloudflare", "cloudflare/cloudflare-python")


class InputMismatch(RuntimeError):
    """A fetched specification is not the one that was pinned."""


class InstrumentUnavailable(RuntimeError):
    """The differ cannot be identified, so nothing measured with it can be attributed."""


@dataclass(frozen=True)
class Instrument:
    """Which differ produced a measurement, in a form a later reader can check.

    The version string alone does not identify the binary. `tools/` is gitignored and populated per
    checkout by `scripts/bootstrap_tools.sh`, which downloads whatever release is latest that day
    rather than a pinned one, so two working copies hold different builds that both call themselves
    oasdiff. The sha256 is what makes a recorded number attributable to an exact file.
    """

    version: str
    sha256: str


def read_instrument(binary: Path) -> Instrument:
    """Identify the differ, or refuse.

    Every failure here raises rather than returning a blank: a measurement carrying an empty
    version looks recorded and identifies nothing, which is worse than one that never ran.

    `encoding="utf-8"` is not decoration. Without it a decode error on this boundary is raised on
    the reader thread, never propagates, and returns `stdout` as `None`.
    """
    if not binary.exists():
        raise InstrumentUnavailable(f"{binary} is missing")

    result = subprocess.run(
        [str(binary), "--version"], capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode != 0:
        raise InstrumentUnavailable(
            f"{binary} --version failed ({result.returncode}): "
            f"{(result.stderr or '').strip()[:200]}"
        )

    version = (result.stdout or "").strip()
    if not version:
        raise InstrumentUnavailable(f"{binary} --version reported no version")

    return Instrument(version=version, sha256=hashlib.sha256(binary.read_bytes()).hexdigest())


def gh_raw(repo: str, path: str, ref: str) -> bytes:
    """A file's bytes at a commit, through the authenticated `gh` CLI.

    The raw Accept header rather than the default JSON envelope: `vercel-spec.json` is 9 MB and the
    envelope's base64 `.content` field is capped at 1 MB, so the default form returns an empty
    string for exactly the file this needs. No `text=True` round trip, so a console's non-UTF-8
    default cannot corrupt the bytes.
    """
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/contents/{path}?ref={ref}",
         "--header", "Accept: application/vnd.github.raw"],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{repo}@{ref[:12]} {path}: gh failed: "
            f"{result.stderr.decode('utf-8', errors='replace').strip()}"
        )
    return result.stdout


def _get(url: str, timeout: float = 120.0) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "sync-noise-measurement"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read()


def specification(version: SpecVersion) -> Path:
    """A verified local copy of one side's specification, fetched only if it is not already here.

    A cached file that fails its pin is a failure and not a cache miss: silently replacing it would
    hide whatever wrote the wrong bytes.
    """
    if version.path.exists():
        _verify(version, version.path.read_bytes())
        return version.path

    if version.blob_path is not None:
        data = gh_raw(version.repo, version.blob_path, version.ref)
    else:
        assert version.manifest is not None
        source = parse_manifest(
            version.manifest,
            gh_raw(version.repo, version.manifest, version.ref).decode("utf-8"),
        )
        if source is None or source.spec_url is None:
            raise InputMismatch(
                f"{version.repo}@{version.ref[:12]} {version.manifest} names no fetchable "
                f"specification"
            )
        data = _get(source.spec_url)

    _verify(version, data)
    version.path.parent.mkdir(parents=True, exist_ok=True)
    version.path.write_bytes(data)
    return version.path


def _verify(version: SpecVersion, data: bytes) -> None:
    found = hashlib.sha256(data).hexdigest()
    if found != version.sha256:
        raise InputMismatch(
            f"{version.filename}: expected sha256 {version.sha256}, got {found} "
            f"({len(data)} bytes from {version.repo}@{version.ref[:12]})"
        )


def run_once(base: Path, revision: Path) -> tuple[list[dict], float]:
    """One `oasdiff breaking`, exactly as `run_oasdiff_breaking` invokes it.

    `encoding="utf-8"` is not decoration: without it a decode error on this boundary is raised on
    the reader thread, never propagates, and returns `stdout` as `None` -- so the failure would
    arrive as a `TypeError` somewhere unrelated rather than here.
    """
    started = time.monotonic()
    result = subprocess.run(
        [str(BINARY), "breaking", str(base), str(revision), "--format", "json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    elapsed = time.monotonic() - started
    if result.returncode != 0:
        sys.exit(f"oasdiff failed ({result.returncode}): {result.stderr.strip()[:400]}")
    return json.loads(result.stdout), elapsed


def operation_keys(records: list[dict]) -> set[tuple[str, str, str]]:
    """`(kind, path, operationId)` -- the level `2026-07-29-oasdiff-determinism.md` measured as
    nested, and the level at which coverage rather than row volume is counted."""
    return {(r.get("id", ""), r.get("path", ""), _operation_id(r)) for r in records}


def operations(records: list[dict]) -> set[tuple[str, str]]:
    """Which operations a record set touches at all, with the rule id dropped.

    This is what a filter can cost. A kind carrying operations no other kind reaches is a kind that
    loses coverage when dropped, which is the distinction §4 of the determinism report drew between
    where the volume sits and where the findings sit.
    """
    return {(r.get("path", ""), _operation_id(r)) for r in records}


def _operation_id(record: dict) -> str:
    return record.get("operationId") or (
        f"{record.get('operation', '')} {record.get('path', '')}".strip()
    )


def measure(pair: Pair, runs: int) -> dict:
    base = specification(pair.base)
    head = specification(pair.head)

    print(f"\n=== {pair.vendor_id}  {pair.label}")
    print(f"    {base.name}\n -> {head.name}")

    header = (
        f"{'run':>4} {'records':>9} {'kinds':>6} {'new':>4} {'ops':>6} {'op keys':>8} "
        f"{'new':>5} {'nested':>7} {'secs':>6}"
    )
    print(header)
    print("-" * len(header))

    kind_union: set[str] = set()
    op_key_union: set[tuple[str, str, str]] = set()
    per_run: list[collections.Counter] = []
    levels: dict[str, int] = {}
    lost_operations: list[int] = []
    curve = []

    for index in range(1, runs + 1):
        records, elapsed = run_once(base, head)
        counts = collections.Counter(r.get("id", "unknown") for r in records)
        for record in records:
            levels.setdefault(record.get("id", "unknown"), record.get("level"))

        keys = operation_keys(records)
        new_kinds = len(set(counts) - kind_union)
        new_keys = len(keys - op_key_union)
        nested = keys <= op_key_union or op_key_union <= keys if op_key_union else True

        # What dropping the candidate kind would cost this run in coverage, not in volume.
        kept = [r for r in records if r.get("id") != CANDIDATE]
        lost_operations.append(len(operations(records) - operations(kept)))

        kind_union |= set(counts)
        op_key_union |= keys
        per_run.append(counts)
        curve.append({
            "run": index, "records": len(records), "kinds": len(counts),
            "new_kinds": new_kinds, "operations": len(operations(records)),
            "op_keys": len(keys), "new_op_keys": new_keys, "nested": nested,
            "seconds": round(elapsed, 2),
            "candidate_records": counts.get(CANDIDATE, 0),
            "operations_lost_to_candidate": lost_operations[-1],
        })
        print(
            f"{index:>4} {len(records):>9,} {len(counts):>6} {new_kinds:>4} "
            f"{len(operations(records)):>6,} {len(keys):>8,} {new_keys:>5} "
            f"{str(nested):>7} {elapsed:>6.2f}"
        )
        sys.stdout.flush()

    totals = collections.Counter()
    for counts in per_run:
        totals.update(counts)
    grand = sum(totals.values())

    print(f"\n{'rule id':<48} {'records':>9} {'share':>7} {'per-run share':>16} {'level':>6}")
    print("-" * 90)
    for kind, total in totals.most_common():
        shares = [counts.get(kind, 0) / max(sum(counts.values()), 1) for counts in per_run]
        print(
            f"{kind:<48} {total:>9,} {total / grand:>6.1%} "
            f"{min(shares):>7.1%}-{max(shares):<8.1%} {levels.get(kind)!s:>6}"
        )

    candidate_share = totals.get(CANDIDATE, 0) / grand if grand else 0.0
    print(
        f"\n{runs} runs. {CANDIDATE} is {candidate_share:.1%} of records across them. "
        f"Operations lost if it were dropped: "
        f"{min(lost_operations)}-{max(lost_operations)} per run."
    )
    return {
        "vendor_id": pair.vendor_id, "label": pair.label, "runs": runs,
        "base": pair.base.filename, "head": pair.head.filename,
        "totals": dict(totals), "levels": levels, "candidate_share": candidate_share,
        "operations_lost_to_candidate": lost_operations, "curve": curve,
    }


def report_not_fetchable() -> dict:
    vendor_id, repo = NOT_FETCHABLE
    source = parse_manifest(".stats.yml", gh_raw(repo, ".stats.yml", "HEAD").decode("utf-8"))
    fetchable = source is not None and source.is_fetchable
    print(
        f"\n=== {vendor_id}  no pair to measure\n"
        f"    {repo} .stats.yml is_fetchable={fetchable}, "
        f"endpoints={source.endpoint_count if source else None}"
    )
    if fetchable:
        print("    THIS HAS CHANGED: the vendor now publishes a URL and has an unmeasured exposure.")
    return {"vendor_id": vendor_id, "is_fetchable": fetchable,
            "endpoint_count": source.endpoint_count if source else None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=12)
    parser.add_argument("--vendor", help="measure one vendor's pairs only")
    parser.add_argument("--out", type=Path, default=None, help="write the measurement as JSON")
    args = parser.parse_args()

    try:
        instrument = read_instrument(BINARY)
    except InstrumentUnavailable as unusable:
        sys.exit(f"{unusable}; run scripts/bootstrap_tools.sh")
    print(f"{instrument.version}  sha256 {instrument.sha256}")

    wanted = [p for p in PAIRS if args.vendor is None or p.vendor_id == args.vendor]
    results = [measure(pair, args.runs) for pair in wanted]

    unfetchable = None
    if args.vendor in (None, NOT_FETCHABLE[0]):
        unfetchable = report_not_fetchable()

    if args.out:
        args.out.write_text(
            json.dumps({"instrument": {"version": instrument.version,
                                       "sha256": instrument.sha256},
                        "pairs": results, "not_fetchable": unfetchable},
                       indent=1),
            encoding="utf-8",
        )
        print(f"\nwritten to {args.out}")


if __name__ == "__main__":
    main()
