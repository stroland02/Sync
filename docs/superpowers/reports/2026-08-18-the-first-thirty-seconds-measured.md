# The first thirty seconds, measured

**2026-08-18, Lane C, `CI-W385`.** Decision 32 says the demo *opens* by typing the install command.
Nobody had timed it. Measured on this host, against the image a stranger's clone would produce.

| | seconds |
|---|---|
| Cold build, `--no-cache` | **282** (4m 42s) |
| Bring-up once the image exists, `up -d --wait` | **22** |
| **Cold total** | **~304** (5m 4s) |
| **Warm total** | **22** |

## The finding, and it is a scheduling decision rather than an engineering one

**Warm, this is a twenty-two second opening and it does what decision 32 asks.** Cold, it is five
minutes of build log in front of an audience, and the thing being shown is a package manager.

Nothing here is slow for a bad reason. The 282 seconds is `npm ci` over the console's dependency
tree, a Vite production build, an `apt` install of Node into the runtime image, and `uv sync` over
the Python tree — four toolchains, each doing real work once. Shaving it is possible and it is not
where the win is: **the win is not paying it in the room.**

## What to do about it, in order of how much it costs

1. **Build the image before the meeting.** Free, and it turns 5m 4s into 22s. `docker compose -f
   docker-compose.demo.yml build` on the machine that will be shown, at any point beforehand. This
   is the whole fix for Wednesday and it requires no decision from anybody.
2. **Publish the image.** Then `npx` pulls rather than builds and a stranger gets the same 22
   seconds on a machine that has never seen this repository. That needs a registry, credentials and
   a spend, so it is the owner's call rather than this lane's — recorded here rather than assumed.
3. **Shrink the build.** Copying Node from the official image instead of installing it through
   NodeSource, and pruning dev dependencies from the console stage, would take a bite out of the
   282. It is the least valuable of the three: it makes the number nobody should be paying smaller.

## The healthcheck, and why it asks for 401

The `sync` service had none, so `docker compose up --wait` returned as soon as the container
started rather than when the console could answer, and the doorbell had to guess. It now polls the
console and requires **401** specifically.

**A check that accepted any response would pass on the error page.** Unauthenticated is what a
healthy console returns to a request carrying no credential, so 401 is the narrowest answer that
means "serving, and the gate is in front of it" — the same reason the CI job asserts the shape of
the API's body rather than its status.

`start_period` is 60s and covers the entrypoint's real work — waiting for Postgres, applying the
schema, starting the API, waiting for the API to answer — during which failures are not counted, so
a slow first boot is not marked unhealthy before it has had its chance.

Measured after adding it: `up -d --wait` reported `sync-demo-sync-1 Healthy` and returned in 22
seconds, and the console answered 200 immediately afterwards.
