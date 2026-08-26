"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

export type ThemeChoice = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

export const THEME_STORAGE_KEY = "docmate.theme";

/**
 * Blocking script injected into <head> so the correct palette is painted on the
 * very first frame (no white flash before hydration). Kept dependency-free and
 * defensive — a locked-down browser that throws on localStorage still renders.
 */
export const themeInitScript = `(function(){try{var k=${JSON.stringify(
  THEME_STORAGE_KEY,
)};var s=null;try{s=localStorage.getItem(k)}catch(e){}var m=window.matchMedia("(prefers-color-scheme: dark)").matches;var d=s==="dark"||((s===null||s==="system")&&m);document.documentElement.classList.toggle("dark",d);document.documentElement.style.colorScheme=d?"dark":"light";}catch(e){}})();`;

type ThemeContextValue = {
  /** What the user picked (may be "system"). */
  theme: ThemeChoice;
  /** What is actually being rendered right now. */
  resolved: ResolvedTheme;
  setTheme: (theme: ThemeChoice) => void;
  /** Cycle light → dark → system. */
  cycleTheme: () => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

function readStored(): ThemeChoice {
  try {
    const raw = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (raw === "light" || raw === "dark" || raw === "system") return raw;
  } catch {
    /* private mode / blocked storage — fall through to system */
  }
  return "system";
}

function systemPrefersDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function apply(resolved: ResolvedTheme) {
  const root = document.documentElement;
  root.classList.toggle("dark", resolved === "dark");
  root.style.colorScheme = resolved;
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  // Server render assumes light; the head script has already fixed the DOM, and
  // the mount effect below syncs React state to the real stored preference.
  const [theme, setThemeState] = useState<ThemeChoice>("system");
  const [resolved, setResolved] = useState<ResolvedTheme>("light");

  useEffect(() => {
    const stored = readStored();
    setThemeState(stored);
    const next: ResolvedTheme =
      stored === "system" ? (systemPrefersDark() ? "dark" : "light") : stored;
    setResolved(next);
    apply(next);
  }, []);

  // Follow the OS while the choice is "system".
  useEffect(() => {
    if (theme !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      const next: ResolvedTheme = mq.matches ? "dark" : "light";
      setResolved(next);
      apply(next);
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [theme]);

  const setTheme = useCallback((next: ThemeChoice) => {
    setThemeState(next);
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      /* preference simply won't persist */
    }
    const applied: ResolvedTheme =
      next === "system" ? (systemPrefersDark() ? "dark" : "light") : next;
    setResolved(applied);
    apply(applied);
  }, []);

  const cycleTheme = useCallback(() => {
    setTheme(theme === "light" ? "dark" : theme === "dark" ? "system" : "light");
  }, [theme, setTheme]);

  const value = useMemo<ThemeContextValue>(
    () => ({ theme, resolved, setTheme, cycleTheme }),
    [theme, resolved, setTheme, cycleTheme],
  );

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return ctx;
}
