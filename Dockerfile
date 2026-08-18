# The product as one image: the API, the console, and the Python toolchain.
#
# Sync is Python and TypeScript over Postgres, so `npx` cannot ship it -- npm delivers a Node
# program and nothing else, and a wrapper that pretends otherwise fails in front of the person
# being shown it. Docker can ship all three. That is the whole argument for this file: one stated
# prerequisite instead of three, which is the only honest route from three commands to one.
#
# Two stages, because the console is a build artifact and its toolchain is not needed at runtime
# to serve it -- only Node itself is, for `web/scripts/serve-console.mjs`, which owns the `/api`
# proxy and the credential gate and is not reimplemented here.

FROM node:22-slim AS console

WORKDIR /build

# The lockfile alone first, so a source edit does not re-resolve the dependency tree. `npm ci`
# rather than `npm install`: it installs exactly what the lockfile pins and fails if the manifest
# and the lockfile disagree, which is the property a reproducible image needs.
COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web/ ./
RUN npm run build


FROM python:3.12-slim AS runtime

# Node is a runtime dependency, not a build one: `serve-console.mjs` serves the built console and
# proxies `/api` to the API in this same image. Taken from NodeSource rather than Debian's own
# package, which is several major versions behind what `web/` is written against.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
 && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && apt-get purge -y gnupg \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

# `uv` only, per CLAUDE.md. Copied from its published image rather than curled, so the version in
# the image is a thing the tag records rather than whatever the installer served that day.
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:${PATH}"

# The source arrives before the install, and the usual dependencies-first layer trick is
# deliberately not used here. `[tool.uv.workspace]` names `src` as a member, so `sync-core` is a
# path dependency that uv *builds* -- `--no-install-project` skips the root project only, not a
# workspace member, and the build needs that member's full source including its own README. The
# two-step form failed on exactly that. One honest step beats a cache layer that cannot work.
#
# `--frozen` refuses to update the lockfile, so the image cannot silently ship a different
# dependency tree from the one this repository pins.
# `LICENSE` is not decoration here: both manifests declare `license-files = ["LICENSE"]`, and the
# build backend fails outright when the glob matches nothing.
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src/ ./src/
RUN uv sync --frozen --no-dev

COPY scripts/ ./scripts/
COPY web/scripts/ ./web/scripts/
COPY --from=console /build/dist ./web/dist

COPY docker/entrypoint.sh /usr/local/bin/sync-up
RUN chmod +x /usr/local/bin/sync-up

# The console's port. The API's is deliberately not published by the compose file that runs this:
# nothing outside needs to reach it, and the console proxies what does.
EXPOSE 4173

ENTRYPOINT ["/usr/local/bin/sync-up"]
