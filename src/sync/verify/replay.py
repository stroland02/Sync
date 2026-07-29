"""Steps 2 and 3 of the replay tier: run the patched call path, and check what it read.

`docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md` states the gap this
closes, and it is not a gap in `tsc`:

    a green CI run proves little when no test exercises the patched call. Most customers have
    no test covering their Stripe integration; a passing suite that never runs the patched
    path is weak evidence presented as strong.

`mock_response` is step 1 and produces a body from the new specification and the observed
baseline. This executes the patched call against that body and asserts two things: that the
code consumed it without throwing, and that every field `response_fields_read` records is
actually in it. Those are different failures. Code can consume a response cleanly while
reading a field that is now absent -- `result.status` on an object with no `status` is
`undefined` and throws nothing at all -- so the second check is not implied by the first.

What executes, and what does not
--------------------------------
The patched module is imported and **one named export is called**. That is the call path. The
customer's server is not started, their test suite is not run, no entry point is executed, and
no lifecycle script runs -- replay never installs anything, because the vendor package is
intercepted before resolution rather than loaded from the tree.

The export has to be named by the caller. `CallSite` records the file, line, column and symbol
of the call and not the function that encloses it, so nothing here can derive it; a caller that
cannot name one does not call this. Resolving it would mean walking the module in
`sync.index`, which owns that parsing.

TypeScript is executed by Node's own type stripping rather than by a transpiler. That is worth
one sentence because of what it avoids: no `tsx`, no `ts-node`, and above all no package
fetched over the network at verification time, which is the reproducibility defect the threat
model already records against `--package=typescript@latest`. The cost is Node's constraint --
erasable syntax only, so a file using enums or namespaces declines rather than running.

The sandbox
-----------
`CLAUDE.md` is qualified about this and so is the spec: replay "executes customer code only
inside the sandbox the threat model requires for `tsc` already -- this adds no new execution
surface, only new use of one that must exist anyway." Four rules, each enforced rather than
documented, and each with a test that proves the enforcement:

**No network.** The mock is the only response. `fetch` and `WebSocket` are replaced before the
customer's module loads, and every networking builtin resolves to a module that throws on
import. A call path that reaches for the vendor fails replay rather than reaching it.

**No credential.** The child is given an environment built from nothing, with an allowlist of
variable *names* the platform needs to start a process at all. Whatever this process holds does
not reach it. Where the call path needs a key to run, `credential_env` supplies
`SYNTHETIC_CREDENTIAL`, which is not key-shaped and cannot authenticate anywhere.

**No writes and no subprocesses.** Node's permission model is on with neither
`--allow-fs-write` nor `--allow-child-process`, so the call path cannot leave a side effect
behind or escape into a shell. Reads are scoped to the clone and to the harness.

**Nothing is written into the clone.** The harness lives in a temporary directory and is
removed afterwards. That matters beyond tidiness: `sync.index.dependency_edits` fails a
verification when a file under an installed dependency has moved, and `shipped_tree` measures
the tree a push would carry. A replay tier that dropped files into the clone would break the
gate that runs beside it.

The hooks are registered with `module.registerHooks`, which runs in the loading thread. The
asynchronous `module.register` spawns a worker, and a worker is precisely what the permission
model denies -- so the synchronous form is not a style preference, it is what lets the sandbox
stay closed.

What this returns and does not do
---------------------------------
It does not write to the shape store. The spec notes every replay run is also a writer with
`source = 'replay'`, and `ReplayResult.shapes` carries exactly those rows for a caller that
holds the store to write in one step. Two honest qualifications travel with them: they describe
the mock the code was exercised against rather than traffic a vendor sent, and `source` is part
of the store's natural key precisely so a replay row can never merge into an error-payload one
and be read later as evidence about a real response.

It returns no value the customer's code produced. The harness reports an outcome and, on a
throw, the error message; the return value stays in the child. Step 3 needs the mock and the
indexed field list, both of which this process already holds, so nothing is gained by carrying
a customer's data back across the boundary and something is risked.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from sync.core import CallSite, ObservedShape, RepoRef
from sync.signals.sentry.shapes import walk

# Not a credential with the wrong value -- not credential-shaped at all. A placeholder that
# looked like a key would eventually be pasted into an issue as one, which is the same
# argument `mock_response.PLACEHOLDER_PREFIX` makes about synthetic strings.
SYNTHETIC_CREDENTIAL = "<sync-replay-not-a-credential>"

# What the shape store files these rows under. Part of its natural key, so replay rows sit
# beside observed ones rather than merging into them.
REPLAY_SOURCE = "replay"

# A call path that has not returned by now is not going to. Long enough that a slow import is
# not mistaken for a hang, short enough that a run cannot sit behind an accidental `await` on
# something that will never resolve.
_TIMEOUT_SECONDS = 60.0

# Environment variable *names* the child keeps, never values this process was given for its own
# work. `SystemRoot` and `windir` are what Windows needs to start a process at all; `PATH` is
# how Node finds its own helpers. Nothing on this list carries a secret, and a variable not on
# it does not exist as far as the call path is concerned.
_ENVIRONMENT_ALLOWLIST = (
    "PATH", "PATHEXT", "SystemRoot", "SYSTEMROOT", "windir", "COMSPEC", "TEMP", "TMP",
)

# Networking builtins, in both spellings the resolver sees.
_NETWORK_BUILTINS = (
    "net", "http", "https", "http2", "dgram", "tls", "dns", "dns/promises",
)

Outcome = Literal["passed", "threw", "unsatisfied", "declined", "timed-out"]

_MARKER = "SYNC_REPLAY_RESULT "


@dataclass(frozen=True)
class ReplayResult:
    """What one replay run established, and what it could not.

    `outcome` is the whole answer and `ok` is shorthand for one value of it. The distinction
    that matters to a caller is `declined`: it means the run never happened, so it is evidence
    of nothing -- neither a defect in the patch nor a reason to pass one. Treating a decline as
    a green replay would put "the patched path was executed" in a pull request body when
    nothing was executed, which is the failure this whole tier exists to argue against.
    """

    outcome: Outcome
    reason: str = ""
    missing_fields: tuple[str, ...] = ()
    shapes: tuple[ObservedShape, ...] = ()

    @property
    def ok(self) -> bool:
        return self.outcome == "passed"


def unsatisfied_fields(body: Any, fields: Sequence[str]) -> tuple[str, ...]:
    """Which recorded reads the mock does not satisfy, in the order they were recorded.

    Step 3, and pure. `response_fields_read` is dot-separated -- `sync.index.typescript` joins
    a member chain with `.` -- so this walks that form. Reading it as a JSON Pointer would
    match nothing and report every nested field as missing, which is a gate that fails
    everything and therefore proves nothing.

    A field that is present and null is satisfied. The field is there; whether the code
    survives the null is the execution step's question and it asks it separately.
    """
    return tuple(field for field in fields if not _reaches(body, field))


def _reaches(body: Any, field: str) -> bool:
    current = body
    for segment in field.split("."):
        if not isinstance(current, Mapping) or segment not in current:
            return False
        current = current[segment]
    return True


def replay_shapes(vendor_id: str, operation_id: str, body: Any) -> tuple[ObservedShape, ...]:
    """The `source='replay'` rows one run produces, for a caller holding the store to write.

    Reduced through `ObservedShape.from_observation`, which is the one place a value is turned
    into a shape and the one place tested for not retaining one. No enum member is retained:
    that argument needs the published specification, this has only the body, and inventing
    provenance is what the column's own comment forbids.

    Deduplicated on `(field_path, json_type)` because that is the store's grain below `source`,
    and because an array of several elements yields one path repeatedly.
    """
    seen: dict[tuple[str, str], ObservedShape] = {}
    for pointer, value in walk(body):
        shape = ObservedShape.from_observation(
            vendor_id, operation_id, pointer, value, REPLAY_SOURCE,
        )
        key = (shape.field_path, shape.json_type)
        existing = seen.get(key)
        if existing is None:
            seen[key] = shape
        elif shape.nullable_seen and not existing.nullable_seen:
            seen[key] = shape
    return tuple(seen.values())


def replay_call_path(
    repo: RepoRef,
    site: CallSite,
    mock: Any,
    *,
    export: str,
    vendor_packages: Sequence[str],
    arguments: Sequence[Any] = (),
    credential_env: Sequence[str] = (),
    timeout: float = _TIMEOUT_SECONDS,
) -> ReplayResult:
    """Execute the patched call path against `mock`, then check what the code reads.

    `vendor_packages` are the bare specifiers to intercept. They are the caller's to name
    rather than derived from `site.vendor_id`: which package a vendor publishes under is
    vendor knowledge, and `CLAUDE.md` keeps that in adapters. Nothing is intercepted by
    default, and a call path whose vendor package is not named would resolve the real SDK and
    then fail on the first network call -- a refusal, but the wrong one to report.

    Ordering is deliberate. Execution runs first and its verdict wins, because "the code threw"
    names a defect a reviewer can act on, while an unsatisfied field on a path that never ran
    is a fact about the mock. Only a run that completed is asked the second question.
    """
    node = shutil.which("node")
    if node is None:
        return ReplayResult("declined", "node is not on PATH, so no call path can be executed")

    module = Path(repo.local_path).resolve() / site.path
    if not module.is_file():
        return ReplayResult("declined", f"{site.path} is not a file in the clone")

    shapes = replay_shapes(site.vendor_id, site.operation_id, mock)

    with tempfile.TemporaryDirectory(prefix="sync-replay-") as harness_dir:
        harness = Path(harness_dir)
        _write_harness(harness)
        outcome, reason = _run(
            node=node,
            harness=harness,
            clone=Path(repo.local_path).resolve(),
            module=module,
            export=export,
            mock=mock,
            arguments=arguments,
            vendor_packages=vendor_packages,
            credential_env=credential_env,
            timeout=timeout,
        )

    if outcome != "executed":
        return ReplayResult(outcome, reason, shapes=shapes)

    missing = unsatisfied_fields(mock, site.response_fields_read)
    if missing:
        return ReplayResult(
            "unsatisfied",
            "the call path consumed the response and reads fields it no longer carries: "
            + ", ".join(missing),
            missing_fields=missing,
            shapes=shapes,
        )
    return ReplayResult("passed", shapes=shapes)


def replay_from_specification(
    repo: RepoRef,
    site: CallSite,
    schema: Mapping[str, Any],
    observed: Sequence[ObservedShape] = (),
    **kwargs: Any,
) -> ReplayResult:
    """The whole tier: synthesize the mock from step 1, then run steps 2 and 3 against it.

    This is the shape a caller actually holds -- the new operation's schema and whatever the
    store has observed for it -- rather than a body someone already built. `replay_call_path`
    stays separately callable because a caller with a mock in hand should not have to
    reconstruct the inputs that produced it, and because a test of the execution boundary is
    clearer over an explicit body than over a synthesized one.
    """
    from sync.verify.mock_response import synthesize_mock_response

    return replay_call_path(repo, site, synthesize_mock_response(schema, observed), **kwargs)


def _environment(
    mock: Any,
    arguments: Sequence[Any],
    vendor_packages: Sequence[str],
    credential_env: Sequence[str],
    harness: Path,
    module: Path,
    export: str,
) -> dict[str, str]:
    """The child's whole environment, built from an empty dict rather than from `os.environ`.

    The direction is the security property. Copying the parent's environment and removing what
    looks sensitive is a denylist, and a denylist is one unanticipated variable name away from
    handing a customer's key to code Sync is executing on their behalf. Starting empty inverts
    the default: a variable reaches the sandbox because it was named here, and the names here
    are platform plumbing that carries no secret.
    """
    environment = {
        name: os.environ[name] for name in _ENVIRONMENT_ALLOWLIST if name in os.environ
    }
    environment.update({name: SYNTHETIC_CREDENTIAL for name in credential_env})
    environment.update({
        "SYNC_REPLAY_STUB": str(harness / "stub.mjs"),
        "SYNC_REPLAY_DENY": str(harness / "deny-network.mjs"),
        "SYNC_REPLAY_MODULE": str(module),
        "SYNC_REPLAY_EXPORT": export,
        "SYNC_REPLAY_MOCK": json.dumps(mock),
        "SYNC_REPLAY_ARGUMENTS": json.dumps(list(arguments)),
        "SYNC_REPLAY_VENDOR": json.dumps(list(vendor_packages)),
        "SYNC_REPLAY_NETWORK": json.dumps(
            [*_NETWORK_BUILTINS, *(f"node:{name}" for name in _NETWORK_BUILTINS)]
        ),
    })
    return environment


def _run(*, node, harness, clone, module, export, mock, arguments, vendor_packages,
         credential_env, timeout) -> tuple[Outcome | Literal["executed"], str]:
    command = [
        node,
        # Denies child processes, worker threads, addons and every write. Reads are scoped to
        # the two directories a replay legitimately touches.
        "--permission",
        f"--allow-fs-read={clone}",
        f"--allow-fs-read={harness}",
        f"--import={(harness / 'bootstrap.mjs').as_uri()}",
        str(harness / "run.mjs"),
    ]
    try:
        # `encoding` is not optional here. Without it a decode error is raised on the reader
        # thread, never propagates, and returns `stdout` as `None` -- one accented identifier
        # in a customer's project is enough, and the failure surfaces somewhere unrelated.
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=_environment(
                mock, arguments, vendor_packages, credential_env, harness, module, export,
            ),
            cwd=str(clone),
        )
    except subprocess.TimeoutExpired:
        return "timed-out", f"the call path did not return within {timeout:g}s"

    payload = _payload(completed.stdout or "")
    if payload is None:
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        return "declined", (
            "the harness produced no verdict, so nothing was established: "
            + (detail[-1] if detail else f"node exited {completed.returncode}")
        )
    return payload.get("outcome", "declined"), payload.get("reason", "")


def _payload(stdout: str) -> dict[str, Any] | None:
    """The harness's verdict, read from a marked line.

    A marker rather than "parse the last line": the customer's own module may print, and a
    `console.log` in their code must not be able to forge a verdict or destroy one.
    """
    for line in reversed(stdout.splitlines()):
        if line.startswith(_MARKER):
            try:
                return json.loads(line[len(_MARKER):])
            except json.JSONDecodeError:
                return None
    return None


_BOOTSTRAP = """\
// Runs before the customer's module is loaded, which is the only moment these can be closed.
import { registerHooks } from 'node:module';
import { pathToFileURL } from 'node:url';

const deny = () => { throw new Error('SYNC_REPLAY_NETWORK_DENIED: replay has no network'); };
globalThis.fetch = deny;
globalThis.WebSocket = deny;
globalThis.XMLHttpRequest = deny;

const STUB = pathToFileURL(process.env.SYNC_REPLAY_STUB).href;
const DENY = pathToFileURL(process.env.SYNC_REPLAY_DENY).href;
const VENDOR = new Set(JSON.parse(process.env.SYNC_REPLAY_VENDOR));
const NETWORK = new Set(JSON.parse(process.env.SYNC_REPLAY_NETWORK));

// Synchronous by necessity, not by taste: `module.register` runs hooks on a worker thread and
// the permission model denies workers, so the asynchronous form cannot coexist with the
// sandbox this tier depends on.
registerHooks({
  resolve(specifier, context, next) {
    if (VENDOR.has(specifier)) return { url: STUB, shortCircuit: true };
    if (NETWORK.has(specifier)) return { url: DENY, shortCircuit: true };
    return next(specifier, context);
  },
});
"""

_STUB = """\
// The vendor SDK, replaced by the mock. Any construction, any property, any call depth
// answers with the same body, because the shape of the client is not what is under test --
// what the patched code does with the response is.
const BODY = JSON.parse(process.env.SYNC_REPLAY_MOCK);

const make = () => new Proxy(function () {}, {
  // `then` must stay undefined or awaiting the proxy would recurse forever: the runtime
  // probes for it to decide whether a value is a thenable.
  get: (_target, property) => (property === 'then' ? undefined : make()),
  apply: () => Promise.resolve(BODY),
  construct: () => make(),
});

export default make();
export const __sync_replay_stub = true;
"""

_DENY_NETWORK = """\
// Importing this is the refusal. A networking builtin resolves here, so reaching for one
// fails at load rather than at the first packet.
throw new Error('SYNC_REPLAY_NETWORK_DENIED: replay has no network');
"""

_RUN = """\
import { pathToFileURL } from 'node:url';

const emit = (payload) => console.log('SYNC_REPLAY_RESULT ' + JSON.stringify(payload));
const message = (error) => (error && error.message ? error.message : String(error));

try {
  const module = await import(pathToFileURL(process.env.SYNC_REPLAY_MODULE).href);
  const name = process.env.SYNC_REPLAY_EXPORT;
  const call = module[name];
  if (typeof call !== 'function') {
    // Nothing ran, so this is not a verdict on the patch.
    emit({ outcome: 'declined', reason: `${name} is not an exported function` });
  } else {
    // The return value stays here. Step 3 is answered from the mock and the indexed field
    // list, both of which the caller already holds, so carrying a customer's data back
    // across the boundary would buy nothing and risk something.
    await call(...JSON.parse(process.env.SYNC_REPLAY_ARGUMENTS));
    emit({ outcome: 'executed' });
  }
} catch (error) {
  emit({ outcome: 'threw', reason: message(error) });
}
"""

_HARNESS_FILES = {
    "bootstrap.mjs": _BOOTSTRAP,
    "stub.mjs": _STUB,
    "deny-network.mjs": _DENY_NETWORK,
    "run.mjs": _RUN,
}


def _write_harness(harness: Path) -> None:
    """The harness, written outside the clone and removed after the run.

    Outside deliberately. `sync.index.dependency_edits` fails a verification when a file under
    an installed dependency has moved, and `shipped_tree` measures the tree a push would
    carry; a tier that dropped files into the clone would break the gate running beside it.
    """
    for name, body in _HARNESS_FILES.items():
        (harness / name).write_text(body, encoding="utf-8")
