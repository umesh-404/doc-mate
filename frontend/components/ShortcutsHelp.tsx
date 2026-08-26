"use client";

import { Keyboard, X } from "lucide-react";
import { useEffect, useRef } from "react";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export type ShortcutEntry = { keys: string[]; label: string };

/**
 * Modal listing the available keyboard shortcuts (opened with `?`).
 * Hand-rolled rather than pulling in a dialog library: focus is trapped to the
 * panel, Escape closes, and the trigger regains focus on close.
 */
export function ShortcutsHelp({
  open,
  onClose,
  entries,
}: {
  open: boolean;
  onClose: () => void;
  entries: ShortcutEntry[];
}) {
  const { t } = useI18n();
  const panelRef = useRef<HTMLDivElement>(null);
  const restoreRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    restoreRef.current = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key !== "Tab") return;
      // Simple focus trap across the panel's focusable children.
      const focusables = panelRef.current?.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      if (!focusables || focusables.length === 0) return;
      const first = focusables[0]!;
      const last = focusables[focusables.length - 1]!;
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown, true);
    return () => {
      document.removeEventListener("keydown", onKeyDown, true);
      restoreRef.current?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-foreground/40 p-4 backdrop-blur-sm animate-fade-in sm:items-center print:hidden"
      onClick={onClose}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="shortcuts-title"
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        className={cn(
          "w-full max-w-md animate-rise-in overflow-hidden rounded-xl border border-border",
          "bg-surface shadow-float focus:outline-none",
        )}
      >
        <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-3.5">
          <h2
            id="shortcuts-title"
            className="flex items-center gap-2 text-md font-semibold text-foreground"
          >
            <Keyboard className="h-4 w-4 text-primary" aria-hidden />
            {t.shortcuts.title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={t.shortcuts.close}
            className="rounded-md p-1.5 text-muted transition-colors hover:bg-surface-muted hover:text-foreground"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>

        <ul className="flex flex-col divide-y divide-border px-5">
          {entries.map((entry) => (
            <li
              key={entry.label}
              className="flex items-center justify-between gap-4 py-2.5"
            >
              <span className="text-sm text-foreground-subtle">
                {entry.label}
              </span>
              <span className="flex shrink-0 items-center gap-1">
                {entry.keys.map((k) => (
                  <kbd key={k} className="kbd">
                    {k}
                  </kbd>
                ))}
              </span>
            </li>
          ))}
        </ul>

        <p className="border-t border-border bg-surface-muted/50 px-5 py-3 text-xs leading-relaxed text-muted">
          {t.shortcuts.note}
        </p>
      </div>
    </div>
  );
}

/** Discreet, always-visible affordance that opens the overlay. */
export function ShortcutsHint({
  onOpen,
  className,
}: {
  onOpen: () => void;
  className?: string;
}) {
  const { t } = useI18n();
  return (
    <button
      type="button"
      onClick={onOpen}
      title={t.shortcuts.open}
      aria-label={t.shortcuts.open}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-2xs font-medium text-muted",
        "transition-colors hover:bg-surface-muted hover:text-foreground",
        className,
      )}
    >
      <Keyboard className="h-3.5 w-3.5" aria-hidden />
      <span className="hidden sm:inline">{t.shortcuts.hint}</span>
      <kbd className="kbd h-5 min-w-[1.25rem] text-[10px]">?</kbd>
    </button>
  );
}
