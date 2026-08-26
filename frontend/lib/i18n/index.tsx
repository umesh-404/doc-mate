"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import {
  defaultLocale,
  getDictionary,
  locales,
  type Dictionary,
  type Locale,
} from "./dictionaries";

type I18nContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: Dictionary;
};

const I18nContext = createContext<I18nContextValue | null>(null);

const STORAGE_KEY = "docmate.locale";

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(defaultLocale);

  // Restore the preferred locale on mount (client-only).
  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY) as Locale | null;
    if (stored && locales.includes(stored)) {
      setLocaleState(stored);
    }
  }, []);

  // Keep <html lang> in sync so screen readers announce the right language and
  // the Devanagari/Tamil line-height rules in globals.css apply.
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = (next: Locale) => {
    setLocaleState(next);
    window.localStorage.setItem(STORAGE_KEY, next);
  };

  const value = useMemo<I18nContextValue>(
    () => ({ locale, setLocale, t: getDictionary(locale) }),
    [locale],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error("useI18n must be used within an I18nProvider");
  }
  return ctx;
}
