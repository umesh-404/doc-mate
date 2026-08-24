"use client";

import { Languages } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { locales, localeNames, type Locale } from "@/lib/i18n/dictionaries";

export function LanguageSwitcher() {
  const { locale, setLocale } = useI18n();
  return (
    <label className="inline-flex items-center gap-2 text-sm text-muted">
      <Languages className="h-4 w-4" aria-hidden />
      <span className="sr-only">Language</span>
      <select
        value={locale}
        onChange={(e) => setLocale(e.target.value as Locale)}
        className="h-9 rounded-md border border-border bg-surface px-2 text-sm text-foreground focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
      >
        {locales.map((l) => (
          <option key={l} value={l}>
            {localeNames[l]}
          </option>
        ))}
      </select>
    </label>
  );
}
