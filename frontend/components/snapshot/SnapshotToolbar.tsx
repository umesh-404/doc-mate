"use client";

import { BookOpen, Download, Loader2, Printer } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useI18n } from "@/lib/i18n";
import { localeNames } from "@/lib/i18n/dictionaries";
import type { SummaryLang } from "@/lib/api";
import { cn } from "@/lib/utils";

export const SUMMARY_LANGS: SummaryLang[] = ["en", "hi", "ta"];

/**
 * Doctor-facing controls above the snapshot: language toggle (EN/HI/TA),
 * patient-friendly narrative toggle, and export actions (FHIR download + print).
 * Hidden from print output via the `print:hidden` utility. Keyboard equivalents
 * are shown as key caps so the shortcuts are discoverable in place.
 */
export function SnapshotToolbar({
  lang,
  onLang,
  translating,
  plainOpen,
  onTogglePlain,
  onExportFhir,
  exportingFhir,
  onPrint,
}: {
  lang: SummaryLang;
  onLang: (lang: SummaryLang) => void;
  translating: boolean;
  plainOpen: boolean;
  onTogglePlain: () => void;
  onExportFhir: () => void;
  exportingFhir: boolean;
  onPrint: () => void;
}) {
  const { t } = useI18n();

  return (
    <div
      className={cn(
        "flex flex-wrap items-center justify-between gap-x-4 gap-y-3 rounded-lg border border-border",
        "bg-surface px-3 py-2.5 shadow-card sm:px-4 print:hidden",
      )}
    >
      <div className="flex flex-wrap items-center gap-2 sm:gap-3">
        <div className="flex items-center gap-2">
          <span className="hidden text-2xs font-semibold uppercase tracking-[0.08em] text-muted sm:inline">
            {t.snapshot.languageLabel}
          </span>
          <div
            className="inline-flex items-center gap-0.5 rounded-md border border-border bg-surface-muted p-0.5"
            role="group"
            aria-label={t.snapshot.languageLabel}
          >
            {SUMMARY_LANGS.map((l) => (
              <button
                key={l}
                type="button"
                onClick={() => onLang(l)}
                aria-pressed={lang === l}
                className={cn(
                  "min-h-[1.75rem] rounded px-2.5 py-1 text-xs font-medium",
                  "transition-colors duration-150 ease-clinical",
                  "focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring",
                  lang === l
                    ? "bg-primary text-primary-foreground shadow-card"
                    : "text-muted hover:text-foreground",
                )}
              >
                {localeNames[l]}
              </button>
            ))}
          </div>
          {translating && (
            <Loader2
              className="h-4 w-4 animate-spin text-primary"
              aria-label={t.states.loading}
            />
          )}
        </div>

        <button
          type="button"
          onClick={onTogglePlain}
          aria-pressed={plainOpen}
          className={cn(
            "inline-flex min-h-[2rem] items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium",
            "transition-colors duration-150 ease-clinical",
            "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
            plainOpen
              ? "border-primary/40 bg-primary/10 text-primary"
              : "border-border bg-surface text-muted hover:border-border-strong hover:text-foreground",
          )}
        >
          <BookOpen className="h-3.5 w-3.5" aria-hidden />
          {t.snapshot.plainToggle}
          <kbd className="kbd ml-0.5 hidden h-5 min-w-[1.25rem] text-[10px] sm:inline-flex">
            b
          </kbd>
        </button>
      </div>

      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={onExportFhir}
          disabled={exportingFhir}
        >
          {exportingFhir ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
          ) : (
            <Download className="h-3.5 w-3.5" aria-hidden />
          )}
          {t.snapshot.exportFhir}
        </Button>
        <Button variant="secondary" size="sm" onClick={onPrint}>
          <Printer className="h-3.5 w-3.5" aria-hidden />
          {t.snapshot.exportPdf}
          <kbd className="kbd ml-0.5 hidden h-5 min-w-[1.25rem] text-[10px] sm:inline-flex">
            p
          </kbd>
        </Button>
      </div>
    </div>
  );
}
