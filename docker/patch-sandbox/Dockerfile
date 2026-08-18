# sync-patch-sandbox:base -- the image B97's containment runs the patch agent inside.
#
# Built once, off the request path, and reused across every patch attempt: a run pays
# only for `docker create`/`start` against an already-cached local image, not for
# resolving a toolchain from scratch. `docs/superpowers/specs/2026-07-25-sync-latency-
# architecture.md` calls this Lever 2, precomputation.
#
# Root inside the image runs `corepack enable`, so pnpm and yarn are on PATH without
# reproducing this host's unelevated-corepack workaround (CLAUDE.md's toolchain table)
# inside every container. TypeScript is pinned at build time rather than resolved with
# `npx --package=typescript@latest` at verify time, which also closes threat-model
# mitigation 4 and removes a network fetch from the verify step entirely.
#
# `sync.remediate.sandbox` proves the network-cutoff primitive this image would run
# under. `sync.remediate.sandbox_image` (B97 Decision 2) computes a content-hash tag
# for this Dockerfile and its build args, and builds it idempotently -- once at worker
# startup and once on a schedule, never on a real patch attempt's own critical path.
#
# B97 Decision 1: `claude_agent_sdk` (below) is what lets an agent turn run inside this image
# at all -- verified against this exact base, not assumed. `pip install claude_agent_sdk` on
# `python:3.12-slim-bookworm` resolves the Linux-platform wheel, which bundles a real Linux
# `claude` binary at `_bundled/claude` (no `.exe`, the Windows host's own copy) and it runs:
# `claude --version` inside a fresh container from this base printed a real version, no missing
# shared library, no architecture mismatch. `sync.runner.docker_sdk` (not yet written) is the
# in-container driver that calls it; this Dockerfile only proves the binary is reachable.

# Pinned by digest, not by the mutable `python:3.12-slim-bookworm` tag: a content
# hash of this file's bytes is only a meaningful "is my image current" check if the
# base underneath it cannot drift out from under an unchanged tag. Upstream rebuilds
# `python:3.12-slim-bookworm` on its own schedule; pinning the digest makes a base
# bump a deliberate, reviewed edit to this line instead of a silent drift the content
# hash would misreport as unchanged. Resolved 2026-08-16 against Docker Hub; bump
# deliberately, not automatically.
FROM python:3.12-slim-bookworm@sha256:a116514e19457bcb7af7efe9c3dd0b9b71e85b317694e7882a1c52aa15a78134

ARG TYPESCRIPT_VERSION=5.9.3
ARG NODE_MAJOR=22

# curl and gnupg only to fetch and verify NodeSource's setup script; ca-certificates so
# every later `npm`/`pip`/`uv` fetch during the install phase can verify TLS.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg git \
    && curl -fsSL https://deb.nodesource.com/setup_${NODE_MAJOR}.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g typescript@${TYPESCRIPT_VERSION} \
    && corepack enable \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

ARG CLAUDE_AGENT_SDK_VERSION=0.2.128
# Pinned to the version this repository's own pyproject.toml/uv.lock resolve on the host --
# `sync.runner.claude_sdk`'s ClaudeAgentOptions surface is exact-version-sensitive per CLAUDE.md's
# own model-configuration section, and an unpinned image could silently drift to a newer SDK the
# host-side code was never checked against.
RUN pip install --no-cache-dir "claude_agent_sdk==${CLAUDE_AGENT_SDK_VERSION}"

# Non-root: the threat model's mitigation 1 asks for a container with no credential on
# its filesystem and a user that cannot escalate inside it even if a permitted command
# turns out not to be as inert as `sync.remediate.tool_gate` assumed.
RUN useradd --create-home --uid 10001 sandbox
USER sandbox
WORKDIR /workspace

# `--read-only` root filesystem is a run-time flag (`docker create --read-only`), not an
# image property -- it belongs to `sync.remediate.sandbox`'s container creation, not
# here, alongside the memory/CPU ceiling and wall-clock kill this image does not set.

CMD ["sleep", "infinity"]
