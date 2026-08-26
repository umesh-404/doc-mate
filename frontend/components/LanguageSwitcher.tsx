"use client";

import { Languages } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { locales, localeNames, type Locale } from "@/lib/i18n/dictionaries";
import { cn } from "@/lib/utils";

export function LanguageSwitcher({ className }: { className?: string }) {
  const { locale, setLocale } = useI18n();
  return (
    <div className={cn("relative inline-flex items-center", className)}>
      <Languages
        className="pointer-events-none absolute left-2.5 h-3.5 w-3.5 text-muted"
        aria-hidden
      />
      <label htmlFor="locale-switcher" className="sr-only">
        Language
      </label>
      <select
        id="locale-switcher"
        value={locale}
        onChange={(e) => setLocale(e.target.value as Locale)}
        className={cn(
          "h-8 cursor-pointer appearance-none rounded-md border border-control-border bg-surface",
          "py-0 pl-7 pr-2 text-xs font-medium text-foreground-subtle",
          "transition-colors hover:border-accent/70 hover:text-foreground",
          "focus:border-accent focus:outline-none focus:ring-2 focus:ring-ring/35",
        )}
      >
        {locales.map((l) => (
          <option key={l} value={l}>
            {localeNames[l]}
          </option>
        ))}
      </select>
    </div>
  );
}
