/**
 * Resolution order: an explicit stored choice, else `prefers-color-scheme`, else light.
 * `index.html` carries a copy of this same order in an inline script, because it must run
 * before React's module graph loads to avoid a flash of the wrong theme; the two are kept in
 * sync by hand rather than by import, since the inline script cannot import a module.
 */

const STORAGE_KEY = "sync-theme"

export type ThemePreference = "light" | "dark" | "system"
export type EffectiveTheme = "light" | "dark"

function isThemePreference(value: unknown): value is ThemePreference {
  return value === "light" || value === "dark" || value === "system"
}

/** Never throws: a disabled or unavailable `localStorage` (private browsing, a locked-down
 * embed) falls back to "system" rather than leaving the console themeless. */
export function getStoredPreference(): ThemePreference {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    return isThemePreference(stored) ? stored : "system"
  } catch {
    return "system"
  }
}

function storePreference(preference: ThemePreference) {
  try {
    window.localStorage.setItem(STORAGE_KEY, preference)
  } catch {
    // Falls back to "system" on next read, which still resolves to a real theme.
  }
}

function systemPrefersDark(): boolean {
  return (
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
  )
}

export function resolveEffectiveTheme(preference: ThemePreference): EffectiveTheme {
  if (preference === "system") {
    return systemPrefersDark() ? "dark" : "light"
  }
  return preference
}

export function applyEffectiveTheme(effective: EffectiveTheme) {
  document.documentElement.classList.toggle("dark", effective === "dark")
}

let stopSystemListener: (() => void) | undefined

/** Applies `preference`, and — when it is "system" — keeps listening so an OS-level change
 * is followed without a reload. Each call tears down the previous listener first, so at most
 * one is ever live. */
export function applyPreference(preference: ThemePreference) {
  stopSystemListener?.()
  stopSystemListener = undefined

  applyEffectiveTheme(resolveEffectiveTheme(preference))

  if (preference === "system" && typeof window.matchMedia === "function") {
    const query = window.matchMedia("(prefers-color-scheme: dark)")
    const onChange = () => applyEffectiveTheme(systemPrefersDark() ? "dark" : "light")
    query.addEventListener("change", onChange)
    stopSystemListener = () => query.removeEventListener("change", onChange)
  }
}

export function setThemePreference(preference: ThemePreference) {
  storePreference(preference)
  applyPreference(preference)
}

export function initTheme() {
  applyPreference(getStoredPreference())
}
