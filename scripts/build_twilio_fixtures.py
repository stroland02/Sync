"""Rebuild the committed Twilio fixtures from the vendor's published artifacts.

The fixtures are real vendor bytes, reduced. Nothing here invents a change or a symbol:
the specifications come from tags of `twilio/twilio-oai`, and the SDK ground truth comes
from the generated `twilio/twilio-python`, so a test asserting a symbol is asserting
against the library a customer actually imports rather than against our own derivation.

Reduction is necessary because the specifications are a quarter of a megabyte each and the
suite commits two versions. Two different reductions, because the two tests need opposite
halves of the document:

- The change fixtures keep one resource family whole -- paths *and* every schema reachable
  from them -- because `oasdiff` reads schemas to find breaking changes and a dangling
  `$ref` would silently produce fewer records than the vendor's real release did.
- The shape fixture keeps every path and drops every schema, because the symbol map reads
  `operationId` and the `x-twilio` block and never looks inside a schema.

Run it with network access; it is not part of the test suite and no test calls it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SPEC_REPO = "twilio/twilio-oai"
SPEC_PATH = "spec/json/twilio_insights_v1.json"
SDK_REPO = "twilio/twilio-python"

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "twilio"

# Two tags far enough apart to carry real breaking changes. Adjacent tags mostly do not:
# 2.5.0 -> 2.6.9 produces zero, which is why the pair is not simply "the last two".
BASE_TAG = "2.1.0"
REVISION_TAG = "2.3.0"
SHAPE_TAG = "2.6.9"

# One resource family, kept whole. Conferences carries both change kinds the release
# produced -- a request parameter whose type moved, and response enum members added.
KEPT_PATHS = (
    "/v1/Conferences",
    "/v1/Conferences/{ConferenceSid}",
    "/v1/Conferences/{ConferenceSid}/Participants",
    "/v1/Conferences/{ConferenceSid}/Participants/{ParticipantSid}",
)


def fetch(repo: str, path_in_repo: str, ref: str) -> bytes:
    """Raw bytes of a file at a tag, via the authenticated `gh` CLI.

    Bytes, never `text=True`: a specification carries non-ASCII descriptions and the
    platform default on Windows is the locale codepage, which corrupts them silently.
    """
    result = subprocess.run(
        [
            "gh", "api", f"repos/{repo}/contents/{path_in_repo}?ref={ref}",
            "--header", "Accept: application/vnd.github.raw",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"fetch failed for {repo}@{ref}:{path_in_repo}: {result.stderr.decode(errors='replace')}")
    return result.stdout


def _referenced_schemas(node: Any, schemas: dict[str, Any], seen: set[str]) -> None:
    """Collect every schema name reachable from `node`, following refs transitively.

    Transitive because a kept path refs a resource schema which refs its enum schemas. A
    single-level walk drops those, and `oasdiff` reports fewer changes against the trimmed
    pair than against the vendor's real one -- a fixture that quietly understates the
    release it was cut from.
    """
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            name = ref.rsplit("/", 1)[-1]
            if name not in seen:
                seen.add(name)
                _referenced_schemas(schemas.get(name), schemas, seen)
        for value in node.values():
            _referenced_schemas(value, schemas, seen)
    elif isinstance(node, list):
        for value in node:
            _referenced_schemas(value, schemas, seen)


def trim_to_paths(spec: dict[str, Any], kept: tuple[str, ...]) -> dict[str, Any]:
    """One resource family, with every schema it reaches."""
    paths = {path: body for path, body in spec["paths"].items() if path in kept}
    schemas = spec.get("components", {}).get("schemas", {})
    seen: set[str] = set()
    _referenced_schemas(paths, schemas, seen)

    trimmed = {key: value for key, value in spec.items() if key not in ("paths", "components")}
    trimmed["paths"] = paths
    trimmed["components"] = {"schemas": {name: schemas[name] for name in sorted(seen) if name in schemas}}
    return trimmed


def shape_only(spec: dict[str, Any]) -> dict[str, Any]:
    """Every path, stripped to what the symbol map reads.

    Operations keep `operationId` alone; the `x-twilio` block beside them is kept whole
    because `mountName` and `parent` are exactly what the derivation rests on. A path with
    no operations at all is kept rather than dropped -- Twilio publishes two of them, and
    they are the input that makes the map's iteration prove it tolerates one.
    """
    paths: dict[str, Any] = {}
    for path, body in spec["paths"].items():
        kept: dict[str, Any] = {}
        for key, value in body.items():
            if key == "x-twilio":
                kept[key] = value
            elif isinstance(value, dict) and value.get("operationId"):
                kept[key] = {"operationId": value["operationId"]}
        paths[path] = kept
    return {"openapi": spec.get("openapi"), "info": {"title": spec["info"]["title"]}, "paths": paths}


def main() -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)

    # One directory per tag, holding one file per product document. That is the layout the
    # adapter reads, and it is dictated by the vendor: a Twilio version is a tag over 61
    # documents, so a version cannot be a filename the way a Stripe version can.
    for tag in (BASE_TAG, REVISION_TAG):
        spec = json.loads(fetch(SPEC_REPO, SPEC_PATH, tag).decode("utf-8"))
        destination = FIXTURES / tag / "insights_v1.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(trim_to_paths(spec, KEPT_PATHS), indent=1) + "\n", encoding="utf-8"
        )
        print(f"{tag}/insights_v1.json: {destination.stat().st_size} bytes from {SPEC_REPO}@{tag}")

    # Two products, because one product cannot show that a derivation generalises. Messaging
    # is the second because it shares no resource, no naming habit and no nesting depth with
    # Insights, and its thirteen mounts are verifiable against the same generated library.
    for spec_path, name in (
        (SPEC_PATH, "insights_v1_shape.json"),
        ("spec/json/twilio_messaging_v1.json", "messaging_v1_shape.json"),
    ):
        shape = json.loads(fetch(SPEC_REPO, spec_path, SHAPE_TAG).decode("utf-8"))
        (FIXTURES / name).write_text(json.dumps(shape_only(shape), indent=1) + "\n", encoding="utf-8")
        print(f"{name}: {(FIXTURES / name).stat().st_size} bytes from {SPEC_REPO}@{SHAPE_TAG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
