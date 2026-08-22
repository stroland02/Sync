/**
 * The Settings screen's groups, in the order the screen reads them.
 *
 * Its own module so a screen that is not Settings can name a group without importing the page --
 * the Overview's stage grid links here, and a second spelling of these labels would disagree with
 * the group control the first time one is renamed.
 */

export type SettingsGroup =
  | "setup"
  | "model"
  | "pull-requests"
  | "codebases"
  | "adapters"
  | "integrations"
  | "github-connection"
  | "pages"
  | "about"

export interface GroupDef {
  id: SettingsGroup
  label: string
  description: string
}

/**
 * Decision 17's five groups, in decision 17's order.
 *
 * The order is part of the decision rather than a rendering detail: Codebases leads because
 * what this deployment watches precedes what it does when it finds something.
 */
export const SETTING_GROUPS: readonly GroupDef[] = [
  // Setup leads, amending decision 17's order on the owner's 2026-08-18 direction: the
  // checklist is what makes every group below it configurable, and a fresh install reads
  // this screen top-down.
  {
    id: "setup",
    label: "Setup",
    description: "The full loop's prerequisites, probed — and the git remote it addresses",
  },
  // Second, immediately after Setup: it is the one prerequisite the checklist cannot probe its
  // way past, because a deployment with no model connected writes no patch and the owner's
  // ruling is that Sync never inherits the installer's credential to hide that.
  {
    id: "model",
    label: "Model",
    description: "Which model writes the patches, and whose credential pays — yours, never ours",
  },
  {
    id: "codebases",
    label: "Codebases",
    description: "Repository context (.sync/context.md) and analysis rules",
  },
  {
    id: "pull-requests",
    label: "Pull requests",
    description: "Merge policy, merge methods, and base branch automation",
  },
  {
    id: "adapters",
    label: "Adapters",
    description: "Registered signal feeds, adapter inventory, and intake metrics",
  },
  {
    id: "github-connection",
    label: "Connection",
    description: "Forge authentication, local CLI status, and permissions",
  },
  {
    id: "pages",
    label: "Pages",
    description: "How each screen works — the long form behind every ⓘ",
  },
  {
    id: "about",
    label: "About",
    description: "Platform architecture, provenance rungs, adapter tiers, and gates",
  },
] as const

/**
 * The groups a deployment has to reach before the pipeline runs end to end, in the order an
 * operator meets them: what the loop needs, whose model writes the patch, what pushes the branch,
 * and what happens once a patch verifies.
 *
 * Here rather than beside the card that renders it, because it is a fact about Settings. The
 * label is not repeated — `id` is the join, and `stage-pages.test.ts` holds that every id here is
 * one this file declares, so a group renamed or dropped fails the build instead of making a row
 * disappear from the Overview.
 */
export const LOOP_PREREQUISITES: readonly { id: SettingsGroup; why: string }[] = [
  {
    id: "setup",
    why: "The full loop's prerequisites, probed one by one, and the git remote they address.",
  },
  {
    id: "model",
    why:
      "Connect your own frontier model here. The key stays an environment variable this " +
      "deployment reads and never stores — Sync holds no customer secret — so this " +
      "screen reports whether one is present rather than asking you to paste it.",
  },
  {
    id: "github-connection",
    why: "The forge credential a branch is pushed with, and what it is permitted to do.",
  },
  {
    id: "pull-requests",
    why: "What happens once a patch verifies: merge policy, merge method, base branch.",
  },
]
