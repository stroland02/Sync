import type { SupportedModel } from "./models";

// Typechecks as committed. Swapping the literal for the vendor's replacement introduces a
// TS2322 that the pre-patch baseline does not carry, which is exactly what the static gate
// exists to reject -- a mechanically correct edit that this codebase will not compile.

const MODEL: SupportedModel = "claude-old-1";

export function chosenModel(): string {
  return MODEL;
}
