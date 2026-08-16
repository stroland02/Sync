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
# NOT YET WIRED: nothing in `sync.remediate` invokes this image today.
# `sync.remediate.sandbox` proves the network-cutoff primitive this image would run
# under; this Dockerfile is the artifact that primitive is specified against, authored
# and reviewable but not built or run as part of closing this backlog entry. Building
# and pre-warming it is deploy-time work the design this implements explicitly calls
# out as unsolved here.

FROM python:3.12-slim-bookworm

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
