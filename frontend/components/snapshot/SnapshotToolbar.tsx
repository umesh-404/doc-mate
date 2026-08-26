"use client";

import { Download, Loader2, Printer } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useI18n } from "@/lib/i18n";
import { localeNames } from "@/lib/i18n/dictionaries";
import type { SummaryLang } from "@/lib/api";
import { cn } from "@/lib/utils";

export const SUMMARY_LANGS: SummaryLang[] = ["en", "hi", "ta"];

/**
 * Doctor-facing controls above the snapshot: language toggle (EN/HI/TA),
 * patient-friendly narrative toggle, and export actions (FHIR download + print).
 * Hidden from print output via the `print:hidden` utility.
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
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface px-4 py-3 shadow-card print:hidden">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-medium uppercase tracking-wide text-muted">
            {t.snapshot.languageLabel}
          </span>
          <div
            className="inline-flex overflow-hidden rounded-md border border-border"
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
                  "px-2.5 py-1.5 text-xs font-medium transition-colors",
                  lang === l
                    ? "bg-primary text-primary-foreground"
                    : "bg-surface text-muted hover:bg-surface-muted",
                )}
              >
                {localeNames[l]}
              </button>
            ))}
          </div>
          {translating && (
            <Loader2 className="h-4 w-4 animate-spin text-muted" aria-hidden />
          )}
        </div>

        <button
          type="button"
          onClick={onTogglePlain}
          aria-pressed={plainOpen}
          className={cn(
            "rounded-md border px-3 py-1.5 text-xs font-medium transition-colors",
            plainOpen
              ? "border-primary/30 bg-primary/10 text-primary"
              : "border-border bg-surface text-muted hover:bg-surface-muted",
          )}
        >
          {t.snapshot.plainToggle}
        </button>
      </div>

      <div className="flex items-center gap-2">
        <Button variant="secondary" size="sm" onClick={onExportFhir} disabled={exportingFhir}>
          {exportingFhir ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          ) : (
            <Download className="h-4 w-4" aria-hidden />
          )}
          {t.snapshot.exportFhir}
        </Button>
        <Button variant="secondary" size="sm" onClick={onPrint}>
          <Printer className="h-4 w-4" aria-hidden />
          {t.snapshot.exportPdf}
        </Button>
      </div>
    </div>
  );
}
