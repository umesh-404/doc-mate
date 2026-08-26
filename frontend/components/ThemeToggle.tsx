"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { useTheme, type ThemeChoice } from "@/lib/theme";
import { cn } from "@/lib/utils";

/**
 * Three-state appearance control: Light / Dark / System. Rendered as a small
 * segmented group so the current state is visible at a glance rather than
 * hidden behind a toggle whose meaning depends on the current theme.
 */
export function ThemeToggle({ className }: { className?: string }) {
  const { theme, setTheme } = useTheme();
  const { t } = useI18n();

  const options: { value: ThemeChoice; label: string; icon: React.ReactNode }[] =
    [
      { value: "light", label: t.theme.light, icon: <Sun className="h-3.5 w-3.5" /> },
      { value: "dark", label: t.theme.dark, icon: <Moon className="h-3.5 w-3.5" /> },
      {
        value: "system",
        label: t.theme.system,
        icon: <Monitor className="h-3.5 w-3.5" />,
      },
    ];

  return (
    <div
      role="radiogroup"
      aria-label={t.theme.label}
      className={cn(
        "inline-flex items-center gap-0.5 rounded-md border border-border bg-surface-muted p-0.5",
        className,
      )}
    >
      {options.map((o) => {
        const active = theme === o.value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={active}
            title={o.label}
            onClick={() => setTheme(o.value)}
            className={cn(
              "inline-flex h-7 w-7 items-center justify-center rounded",
              "transition-colors duration-150 ease-clinical",
              "focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring",
              active
                ? "bg-surface text-primary shadow-card"
                : "text-muted hover:text-foreground",
            )}
          >
            <span aria-hidden>{o.icon}</span>
            <span className="sr-only">{o.label}</span>
          </button>
        );
      })}
    </div>
  );
}
