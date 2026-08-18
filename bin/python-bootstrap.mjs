/**
 * Getting a pinned Python without asking the machine for one.
 *
 * Decision 98: `uv` fetches a pinned 3.12 and the dependencies. Rejected: a frozen per-platform
 * binary, which needs a build matrix we do not have time for; and requiring Python, which is the
 * Docker problem moved rather than solved. The repository already uses `uv`, so this is the same
 * tool fetching itself rather than a new dependency.
 *
 * **Fetching is the easy half.** The half that breaks a second run is a `uv`, a Python or a
 * virtualenv the machine already has — the same shape as the Postgres lifecycle in
 * `embedded-postgres.mjs`, and for the same reason: a first-run script never reaches those
 * branches, and the demo reaches them the moment anything is run twice.
 *
 * **The rule underneath every decision here: reuse what is provably the same, rebuild what is
 * merely similar.** A virtualenv built from a different lockfile runs dependencies nobody pinned,
 * and the bug that produces cannot be reproduced by whoever reports it. An interpreter of the
 * wrong minor version is not the pinned one this project relies on. Neither failure announces
 * itself, so neither may be adopted quietly.
 *
 * Sameness is decided on a **digest of the lockfile, never its timestamp.** `CLAUDE.md` carries
 * the measurement: 184 of 200 identical-byte rewrites left `st_mtime_ns` untouched, so an mtime
 * comparison fires only when a write happens to cross a tick and reads as flaky when it is
 * actually a check that mostly does not check.
 *
 * Pure functions over probe results. Nothing here downloads, spawns or writes.
 */

/** What to do about a `uv` on the machine. */
export const USE_EXISTING = "use-existing"
export const FETCH = "fetch"

/** What to do about a virtualenv that is already there. */
export const REUSE = "reuse"
export const REBUILD = "rebuild"

/**
 * Whether to use the `uv` already installed, or fetch our own.
 *
 * **Using the machine's `uv` is not installing one**, and the message says so — the same
 * distinction as adopting a Postgres rather than starting it. An installer that reports work it
 * did not do is teaching the reader to discount its output, on the first line.
 *
 * Too old is a fetch rather than an error. `uv` is ours to bootstrap, so a version that cannot do
 * what we need is our problem to solve rather than the reader's to fix.
 */
export function uvVerdict({ foundVersion, minimumVersion }) {
  if (!foundVersion) {
    return {
      action: FETCH,
      message: "No uv on this machine. Fetching it — nothing else is needed from you.",
    }
  }
  if (isOlder(foundVersion, minimumVersion)) {
    return {
      action: FETCH,
      message:
        `uv ${foundVersion} is installed and this needs at least ${minimumVersion}. ` +
        "Fetching a newer one rather than changing the one you have.",
    }
  }
  return {
    action: USE_EXISTING,
    message: `Using the uv ${foundVersion} already on this machine. Nothing was installed.`,
  }
}

/**
 * Whether the virtualenv on disk can be trusted, or has to be built again.
 *
 * Three ways it cannot be trusted and each says which, because they send a reader to different
 * places: no environment at all is a first run; a different lockfile means the dependency tree
 * would not be the pinned one; a different interpreter means the pinned Python guarantee is not
 * being kept.
 *
 * `lockDigest` is a hash of the lockfile as it is now, `recordedDigest` is the one written when
 * the environment was built. **Never mtimes** — see the module docstring.
 */
export function environmentVerdict({
  exists,
  lockDigest,
  recordedDigest,
  pythonVersion,
  wantedPython,
}) {
  if (!exists) {
    return {
      action: REBUILD,
      message: `Creating the Python ${wantedPython} environment and installing dependencies.`,
    }
  }
  if (pythonVersion !== wantedPython) {
    return {
      action: REBUILD,
      message:
        `The existing environment runs Python ${pythonVersion} and this needs ${wantedPython}. ` +
        "Rebuilding it rather than running against the wrong interpreter.",
    }
  }
  if (recordedDigest !== lockDigest) {
    return {
      action: REBUILD,
      message:
        "The lockfile has changed since this environment was built, so its dependencies are not " +
        "the pinned ones. Rebuilding — reusing it would run versions nobody chose.",
    }
  }
  return {
    action: REUSE,
    message:
      `Reusing the Python ${wantedPython} environment already built from this exact lockfile. ` +
      "No dependency resolution, no download.",
  }
}

/**
 * `a` is older than `b`, comparing dotted numeric versions left to right.
 *
 * Deliberately not a semver library: a dependency to compare two of our own strings is a
 * dependency this installer would have to fetch before it can decide whether to fetch anything.
 * Missing components count as zero, so `0.5` is older than `0.5.11`.
 */
export function isOlder(a, b) {
  const left = String(a).split(".").map(Number)
  const right = String(b).split(".").map(Number)
  for (let i = 0; i < Math.max(left.length, right.length); i += 1) {
    const l = left[i] ?? 0
    const r = right[i] ?? 0
    if (l !== r) return l < r
  }
  return false
}
