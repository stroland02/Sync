/**
 * The lifecycle of a Postgres this installer owns.
 *
 * Decision 97 replaced Docker with embedded binaries the installer fetches and runs as a
 * subprocess. That buys a zero-prerequisite install and it hands us the thing Docker was doing for
 * free: **a process lifecycle.** Start, stop, and the orphan a crash leaves behind.
 *
 * The owner named the failure that matters, and it is not the first run. **A Postgres left running
 * after a crash makes the SECOND run worse than the first** — and the second run is the one that
 * happens on stage, after a first attempt that went wrong. So the decisions here are about what to
 * do when something is *already there*, which is the case a first-run script never exercises and
 * nobody tests by hand.
 *
 * Everything below is a pure function over probe results. Nothing spawns a process, opens a socket
 * or downloads anything — those are the caller's, and they are the parts that cannot be tested
 * before Wednesday. What can be tested is every branch of what we do about what it finds.
 *
 * **Nothing here reports an action it did not take.** Adopting a running server is not starting
 * one, reusing a cache is not fetching it, and a record whose process is gone is a crash rather
 * than a clean slate. Each says which, because a line of install output that overstates is the
 * same defect as a screen that does.
 */

/** The action a caller takes about a Postgres that may already be running. */
export const ADOPT = "adopt"
export const REAP = "reap"
export const FRESH = "fresh"

/** The action a caller takes about the 55MB of binaries. */
export const REUSE = "reuse"
export const DOWNLOAD = "download"

/**
 * What to do about the server a previous run recorded.
 *
 * `record` is what the last run wrote down — `{ pid, port, version }` — or `null` if there is no
 * record. `alive` is the caller's probe of whether that pid is a Postgres we started, and it is
 * passed in rather than taken here so every branch below is reachable in a test.
 *
 * The four cases are genuinely different and collapsing any two is how the second run breaks:
 *
 * - **No record.** Nothing to reason about. Start one.
 * - **Record, alive, same version.** Adopt it. Starting a second Postgres on a second port would
 *   work and would leave the first one running forever, which is how a laptop ends up with four.
 * - **Record, alive, different version.** Not ours to adopt: the binaries this run wants are not
 *   the ones serving that port, and adopting would run new schema against an old server. Reap it
 *   by pid and start fresh.
 * - **Record, not alive.** The last run did not shut down cleanly. Starting fresh is right, and
 *   *saying so* is the point — a silent recovery hides that the previous run crashed, and the
 *   crash is the thing worth knowing about.
 */
export function previousRunVerdict({ record, alive, wantedVersion }) {
  if (record === null || record === undefined) {
    return { action: FRESH, message: "No previous server recorded. Starting Postgres." }
  }
  if (!alive) {
    return {
      action: FRESH,
      message:
        `A previous run recorded Postgres on port ${record.port} (pid ${record.pid}) and that ` +
        "process is gone, so it did not shut down cleanly. Starting a fresh one.",
    }
  }
  if (record.version !== wantedVersion) {
    return {
      action: REAP,
      message:
        `Postgres ${record.version} is still running on port ${record.port} (pid ${record.pid}) ` +
        `and this install wants ${wantedVersion}. Stopping it before starting the right one.`,
    }
  }
  return {
    action: ADOPT,
    message:
      `Postgres ${record.version} is already running on port ${record.port} (pid ${record.pid}). ` +
      "Using it — this run started nothing.",
  }
}

/**
 * Whether the binaries have to be fetched.
 *
 * **A reuse announces itself.** A second run that silently re-downloads 55MB and one that silently
 * reuses it look identical from the outside until somebody is on a hotel connection or a metered
 * phone, and then they are very different. The size is stated on the download for the same reason:
 * a progress bar that appears without warning reads as something being wrong.
 *
 * A cache holding the wrong version is not a cache hit. It is fetched, and the message says which
 * version was found so a reader can tell this from a first run.
 */
export function cacheVerdict({ cachedVersion, wantedVersion, sizeMb = 55 }) {
  if (cachedVersion === wantedVersion) {
    return {
      action: REUSE,
      message: `Using the Postgres ${wantedVersion} binaries already downloaded. No download.`,
    }
  }
  if (cachedVersion) {
    return {
      action: DOWNLOAD,
      message:
        `The cache holds Postgres ${cachedVersion} and this install wants ${wantedVersion}. ` +
        `Downloading about ${sizeMb}MB, once.`,
    }
  }
  return {
    action: DOWNLOAD,
    message: `Downloading the Postgres ${wantedVersion} binaries, about ${sizeMb}MB. Once — the next run reuses them.`,
  }
}

/**
 * The line printed when the install finishes, given what actually happened.
 *
 * Assembled from the verdicts rather than written at the end, so it cannot claim a step that was
 * skipped. A run that adopted a server and reused a cache did no downloading and started no
 * database, and the summary a reader takes away has to say that — otherwise the first thing they
 * learn about this installer is that it overstates.
 */
export function summarise({ postgres, cache }) {
  const parts = []
  parts.push(
    postgres.action === ADOPT
      ? "reused the Postgres already running"
      : postgres.action === REAP
        ? "replaced a Postgres from a different version"
        : "started Postgres",
  )
  parts.push(cache.action === REUSE ? "no download" : "downloaded the database binaries")
  return parts.join(", ")
}
