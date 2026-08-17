"""B97 Decision 2: building, tagging, and pre-warming the patch-sandbox image, off a
real remediation run's critical path.

`docker/patch-sandbox/Dockerfile` builds and runs, proven by hand once, but nothing
in this tree built it as part of a run, tagged it reproducibly, or kept it warm --
which meant the first real patch attempt after a deploy would have paid for a
`docker build` on its own critical path. The latency spec's Lever 2
(`docs/superpowers/specs/2026-07-25-sync-latency-architecture.md`) is explicit that
this has to be precomputation instead: "the fastest work is work already finished
when the request arrives."

**Tag by content, not by `latest`.** `compute_image_tag` hashes the Dockerfile's own
bytes together with the build args that select its toolchain versions
(`TYPESCRIPT_VERSION`, `NODE_MAJOR`), so "is the image I'm about to run current" is a
cheap, deterministic `docker image inspect` against a name that changes exactly when
the thing it names changes -- not a trust exercise in whatever happens to be cached
under a mutable tag on a given host.

**That tag's reproducibility rests on the Dockerfile's own `FROM` line being pinned
by digest, not by a mutable tag.** This module does not enforce that -- it hashes
whatever bytes are on disk -- but it is only honest to call the result a content hash
if the base image underneath those bytes cannot drift out from under an unchanged
tag. `docker/patch-sandbox/Dockerfile` is pinned for exactly this reason; see its own
comment.

**Pre-warming is `ensure_image_built` called from two places this module does not
own**: once when the remediation worker process starts, and once on a schedule
(daily is enough -- nothing about this image changes faster than the Dockerfile or
the pinned base digest does), so a locally-evicted image cache is caught before a
patch attempt needs it. Neither call site is built here; this module is the
primitive both would call.

**What this module deliberately does not build.** No registry, no push, no pull from
a remote. Nothing in this repository's CI builds or references a container image
today, and nothing implies more than one worker host exists yet -- a registry ahead
of a second worker is debt with no asset behind it, per CLAUDE.md's own rule ("wait
for the caller"). This is the single-host local build-and-tag mechanism; a registry
is a follow-up sized to whatever worker topology actually gets built.

**The one risk this module does not close.** `docker/patch-sandbox/Dockerfile`'s own
comment already concedes it: `corepack enable` installs the shim, not the package
manager, so a customer project pinning a pnpm or yarn version this image never
pre-fetched still pays a network fetch on first use during the install phase. That
phase is already networked, so this is not a new hole -- only a latency cost this
module's pre-warming does not remove, the same shape as CLAUDE.md's own oasdiff
idempotency exemption: named, scoped, and not papered over as solved.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Mapping

# Docker Engine control-plane calls (`image inspect`) are fast; sized the same as
# `sandbox._DOCKER_TIMEOUT_SECONDS`, but this module keeps its own constant rather
# than importing a private name from a sibling module for one shared number.
_DOCKER_INSPECT_TIMEOUT_SECONDS = 30

# A full build resolves apt, Node, and npm packages over the network -- this is
# precomputation, not a request-path call, so it is sized generously rather than to
# match a control-plane round trip.
_DOCKER_BUILD_TIMEOUT_SECONDS = 600

_IMAGE_REPOSITORY = "sync-patch-sandbox"

_DEFAULT_DOCKERFILE = Path(__file__).resolve().parents[3] / "docker" / "patch-sandbox" / "Dockerfile"

# Mirrors `docker/patch-sandbox/Dockerfile`'s own `ARG` defaults. Kept here rather
# than parsed out of the Dockerfile: the two are allowed to drift only in the
# direction a reviewer can see in one diff hunk, not silently, and parsing `ARG`
# lines back out of a Dockerfile to avoid stating them twice would trade one small
# duplication for a parser this module does not otherwise need.
DEFAULT_BUILD_ARGS: Mapping[str, str] = {
    "TYPESCRIPT_VERSION": "5.9.3",
    "NODE_MAJOR": "22",
}


def _docker(*args: str, timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def compute_image_tag(dockerfile_path: Path, build_args: Mapping[str, str]) -> str:
    """`sync-patch-sandbox:<hash>`, where `<hash>` is a function of `dockerfile_path`'s
    bytes and `build_args` alone -- no Docker daemon involved, so this is safe to call
    on a request path even though `ensure_image_built` is not.

    Build args are hashed by sorted key so the tag does not depend on dict insertion
    order, and each pair is delimited by a byte (`\\0`) that cannot appear in a shell-
    safe `KEY=value` string, so `{"A": "1", "B": ""}` and `{"A": "1B", "": ""}` cannot
    collide by concatenation.
    """
    digest = hashlib.sha256()
    digest.update(dockerfile_path.read_bytes())
    for key in sorted(build_args):
        digest.update(f"\0{key}={build_args[key]}\0".encode("utf-8"))
    return f"{_IMAGE_REPOSITORY}:{digest.hexdigest()[:16]}"


def _image_exists(tag: str) -> bool:
    return _docker("image", "inspect", tag, timeout=_DOCKER_INSPECT_TIMEOUT_SECONDS).returncode == 0


def ensure_image_built(
    dockerfile_path: Path | None = None,
    build_args: Mapping[str, str] | None = None,
    *,
    force: bool = False,
) -> str:
    """The idempotent inspect-or-build a worker startup or a scheduled pre-warm calls.

    Computes the content-hash tag, checks whether an image already carries it
    (`docker image inspect`), and builds only on a miss -- a real remediation run
    calling this after a worker has already pre-warmed the image pays for one cheap
    inspect, never a build. `force=True` skips the inspect and rebuilds
    unconditionally, for an operator who knows the local cache is stale in a way the
    tag cannot express (a corrupted image, not a content change).

    Defaults to `docker/patch-sandbox/Dockerfile` and its own pinned toolchain
    versions (`DEFAULT_BUILD_ARGS`) when a caller does not override them, so the
    zero-argument call is "build the real deploy artifact."
    """
    path = dockerfile_path if dockerfile_path is not None else _DEFAULT_DOCKERFILE
    args = dict(DEFAULT_BUILD_ARGS)
    if build_args:
        args.update(build_args)
    tag = compute_image_tag(path, args)

    if not force and _image_exists(tag):
        return tag

    build_args_flags = []
    for key in sorted(args):
        build_args_flags += ["--build-arg", f"{key}={args[key]}"]

    result = _docker(
        "build", "-f", str(path), "-t", tag, *build_args_flags, str(path.parent),
        timeout=_DOCKER_BUILD_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise RuntimeError(f"docker build failed for {tag}: {result.stderr.strip()}")
    return tag
