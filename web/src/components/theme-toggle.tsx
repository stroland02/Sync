/**
 * Light, dark, or follow the system. Two states cannot express "follow the system", so this
 * is a three-way radio group rather than a switch.
 */

import { Monitor, Moon, Sun } from "lucide-react"
import { useState } from "react"

import { cn } from "@/lib/utils"
import { getStoredPreference, setThemePreference, type ThemePreference } from "@/lib/theme"

const OPTIONS: ReadonlyArray<{
  value: ThemePreference
  label: string
  Icon: typeof Sun
}> = [
  { value: "light", label: "Light", Icon: Sun },
  { value: "dark", label: "Dark", Icon: Moon },
  { value: "system", label: "System", Icon: Monitor },
]

export function ThemeToggle() {
  const [preference, setPreference] = useState<ThemePreference>(getStoredPreference)

  function choose(next: ThemePreference) {
    setThemePreference(next)
    setPreference(next)
  }

  return (
    <div
      role="group"
      aria-label="Theme"
      className="inline-flex items-center gap-0.5 rounded-[var(--radius-control)] border border-border bg-muted p-0.5"
    >
      {OPTIONS.map(({ value, label, Icon }) => {
        const selected = preference === value
        return (
          <button
            key={value}
            type="button"
            aria-pressed={selected}
            aria-label={label}
            title={label}
            onClick={() => choose(value)}
            className={cn(
              "inline-flex size-6 items-center justify-center rounded-[min(var(--radius-control),4px)] outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
              selected
                ? "bg-background text-foreground"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Icon className="size-3.5" aria-hidden="true" />
          </button>
        )
      })}
    </div>
  )
}
