/**
 * The three roles an integration can play, as data, so the level's header and its panels cannot
 * disagree about which of them has anything attached.
 *
 * `docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md:455-459` (section
 * *M5 — The integration layer*) is the authority for both the role names and the relationship
 * sentence each one carries. They are reproduced here verbatim rather than paraphrased, and
 * `tests/test_console_signals_roles.py` holds them against that table — the console does not get
 * to be a second authority on this vocabulary, for the same reason it does not get to be one on
 * the hierarchy.
 *
 * `source` is what makes the header honest. A role with a path has an integration attached and a
 * panel that queries it; a role with `null` has nothing in this deployment to query at all — no
 * adapter, no configuration table, no row. Those are different facts and the console renders them
 * differently: `attached and quiet` is a fact about traffic, `nothing is attached` is a fact about
 * configuration, and `not-attached-state.tsx` carries why one may never stand in for the other.
 *
 * The union below is not decoration. A role either has a source and no absence to explain, or has
 * an absence and no source — so the page reads `absence` off an unattached role without a
 * fallback, and a fallback that renders an empty explanation cannot be reached because it cannot
 * be written.
 */

interface Role {
  /** The role, spelled as the specification's M5 table spells it. */
  role: string
  /** That row's *Relationship to the graph*, verbatim. */
  relationship: string
}

/** A role this deployment has an integration for, and the read-surface path its panel asks. */
export interface AttachedRole extends Role {
  source: string
  absence: null
}

/** A role nothing in this deployment attaches, and why there is nothing to query. */
export interface UnattachedRole extends Role {
  source: null
  absence: string
}

export type SignalRole = AttachedRole | UnattachedRole

export const VENDOR_ROLE: AttachedRole = {
  role: "Vendor",
  relationship: "A subject. Code calls it; it can break you.",
  source: "/api/repositories/{repo_id}/coverage",
  absence: null,
}

export const SIGNAL_SOURCE_ROLE: AttachedRole = {
  role: "Signal source",
  relationship: "Feeds the graph. Reports that something broke, deployed, or changed.",
  source: "/api/repositories/{repo_id}/observed",
  absence: null,
}

export const HUMAN_SURFACE_ROLE: UnattachedRole = {
  role: "Human surface",
  relationship: "Consumes. Where a finding is delivered and a human answers.",
  source: null,
  absence:
    "No adapter, no configuration table and no row anywhere in this deployment names a " +
    "delivery destination — not a Slack channel, a Linear issue, a Notion page, or a " +
    "configured GitHub surface. This is different from an attached integration that is quiet: " +
    "a quiet integration was asked and had nothing to report, and this one was never asked, " +
    "because nothing exists here to ask.",
}

/** In the specification's order, which is the order the level renders them in. */
export const SIGNAL_ROLES = [VENDOR_ROLE, SIGNAL_SOURCE_ROLE, HUMAN_SURFACE_ROLE] as const

export const ATTACHED_ROLES = SIGNAL_ROLES.filter(
  (role): role is AttachedRole => role.source !== null,
)

export const UNATTACHED_ROLES = SIGNAL_ROLES.filter(
  (role): role is UnattachedRole => role.source === null,
)
