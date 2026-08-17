/**
 * One shared credential, and an honest account of what that is not.
 *
 * Beta scope Ruling 1 shrinks M4's obligation to this: somebody who is not on the owner's machine
 * can reach the console and see their repository's real data, behind one shared credential rather
 * than a user system. This module is the credential half of that, and it is deliberately small,
 * because the honest version of "one shared password" is small.
 *
 * **This is not authentication and nothing here should be read as claiming otherwise.** There is
 * one secret. Everyone who has it is the same principal, so:
 *
 * - There is no identity. A request that passes carries no answer to *who* — the access log can
 *   say a viewer looked, never which viewer.
 * - There is no revocation short of rotating the one secret, which logs out everybody who has it.
 * - There is no audit trail worth the name, for the same reason.
 * - Sharing it is one message. A credential shared with a design partner is a credential that
 *   partner can forward, and nothing here can tell the difference.
 *
 * What it does buy is the one property beta actually needs: the console is not open to the whole
 * internet the moment it is reachable from off this machine. That is a real gain and it is the
 * entire claim.
 *
 * **Comparison is constant-time**, not because a timing attack on a beta console is likely, but
 * because the alternative — `a === b` on a secret — is the kind of thing that is copied into a
 * later system where it does matter. `crypto.timingSafeEqual` needs equal-length buffers and
 * throws otherwise, which itself leaks length through the exception, so the lengths are compared
 * after both sides are hashed to a fixed width rather than before.
 */

import { createHash, timingSafeEqual } from "node:crypto"

/** Fixed-width digest, so the comparison below never branches on a secret's length. */
function widen(value: string): Buffer {
  return createHash("sha256").update(value, "utf8").digest()
}

/**
 * Whether `offered` is the configured credential.
 *
 * Returns false rather than throwing when either side is empty: an empty configured credential is
 * refused at startup by `requireCredential`, and an empty offered one is simply wrong.
 */
export function credentialMatches(offered: string, configured: string): boolean {
  if (offered === "" || configured === "") return false
  return timingSafeEqual(widen(offered), widen(configured))
}

/**
 * The credential the server must run behind, or an explanation of why it cannot start.
 *
 * **Fails closed.** A missing or blank `SYNC_CONSOLE_PASSWORD` stops the server rather than
 * serving the console unprotected, because the failure mode of the alternative is silent: an
 * operator who forgot the variable would get a working console and no gate, and would have no
 * reason to look. A refusal that names the variable is loud and costs one restart.
 *
 * The minimum length is a floor against the credential somebody types to "just test it" and then
 * leaves in place. It is not a strength policy and does not pretend to be one.
 */
export const MINIMUM_CREDENTIAL_LENGTH = 12

export function requireCredential(env: Record<string, string | undefined>):
  | { ok: true; credential: string }
  | { ok: false; reason: string } {
  const raw = env.SYNC_CONSOLE_PASSWORD
  if (raw === undefined || raw.trim() === "") {
    return {
      ok: false,
      reason:
        "SYNC_CONSOLE_PASSWORD is not set. This server will not serve the console without a " +
        "credential in front of it; set the variable and start again.",
    }
  }
  if (raw.length < MINIMUM_CREDENTIAL_LENGTH) {
    return {
      ok: false,
      reason: `SYNC_CONSOLE_PASSWORD is shorter than ${MINIMUM_CREDENTIAL_LENGTH} characters. That floor exists to stop a throwaway test value being left in place, not as a strength policy.`,
    }
  }
  return { ok: true, credential: raw }
}

/**
 * The credential offered by an `Authorization: Basic` header, or null.
 *
 * The username half is ignored on purpose. There is one principal, so a username would be a field
 * with no meaning that a reader could mistake for an identity — which is the exact confusion the
 * module docstring exists to prevent.
 */
export function offeredCredential(header: string | undefined): string | null {
  if (header === undefined) return null
  const [scheme, encoded] = header.split(" ")
  if (scheme?.toLowerCase() !== "basic" || encoded === undefined) return null
  let decoded: string
  try {
    decoded = Buffer.from(encoded, "base64").toString("utf8")
  } catch {
    return null
  }
  const separator = decoded.indexOf(":")
  if (separator === -1) return null
  return decoded.slice(separator + 1)
}
