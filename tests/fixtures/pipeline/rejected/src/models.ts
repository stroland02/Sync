// A codebase that narrowed the model id to the one it uses. Real, and common in a project that
// wants its own allow-list rather than the SDK's whole union -- and it is what makes the tier-0
// swap in `summarise.ts` fail to compile, because the replacement is not a member of this type.
//
// Nothing edits this file. The remediator is scoped to the call site's own path, so the
// declaration stays as it was and the assignment stops agreeing with it.

export type SupportedModel = "claude-old-1";
