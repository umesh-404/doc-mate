"use client";

import { AlertOctagon, AlertTriangle, Info } from "lucide-react";
import { CitationChip } from "@/components/CitationChip";
import { useI18n } from "@/lib/i18n";
import type { AlertLevel, SummaryAlert } from "@/lib/types";
import { cn } from "@/lib/utils";

const levelStyle: Record<
  AlertLevel,
  { wrap: string; icon: React.ReactNode; label: string }
> = {
  critical: {
    wrap: "border-danger/40 bg-danger-surface text-danger",
    icon: <AlertOctagon className="h-4 w-4" aria-hidden />,
    label: "critical",
  },
  warning: {
    wrap: "border-warning/40 bg-warning-surface text-warning",
    icon: <AlertTriangle className="h-4 w-4" aria-hidden />,
    label: "warning",
  },
  info: {
    wrap: "border-border bg-surface-muted text-muted",
    icon: <Info className="h-4 w-4" aria-hidden />,
    label: "info",
  },
};

const order: Record<AlertLevel, number> = { critical: 0, warning: 1, info: 2 };

/**
 * The first thing the doctor sees: surfaced alerts (allergies, potential
 * interactions, abnormal labs, missing data), critical first. Every alert is a
 * verification prompt with citation chips — never a directive or a diagnosis.
 */
export function AlertsBanner({ alerts }: { alerts: SummaryAlert[] }) {
  const { t } = useI18n();
  if (!alerts || alerts.length === 0) return null;

  const sorted = [...alerts].sort((a, b) => order[a.level] - order[b.level]);

  return (
    <div className="flex flex-col gap-2" role="region" aria-label={t.snapshot.alertsTitle}>
      <div className="flex items-center gap-2 px-1">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">
          {t.snapshot.alertsTitle}
        </h2>
        <span className="text-xs text-muted">({alerts.length})</span>
      </div>
      <ul className="flex flex-col gap-2">
        {sorted.map((alert, i) => {
          const s = levelStyle[alert.level];
          return (
            <li
              key={i}
              className={cn(
                "flex flex-wrap items-start justify-between gap-3 rounded-lg border px-4 py-3 shadow-card",
                s.wrap,
              )}
            >
              <div className="flex min-w-0 items-start gap-2.5">
                <span className="mt-0.5 shrink-0">{s.icon}</span>
                <p className="text-sm font-medium leading-relaxed text-foreground">
                  {alert.text}
                </p>
              </div>
              {alert.citations.length > 0 && (
                <div className="flex shrink-0 flex-wrap items-center gap-1.5">
                  {alert.citations.map((c, ci) => (
                    <CitationChip
                      key={`${c.document_id}-${ci}`}
                      label={c.label}
                      documentId={c.document_id}
                    />
                  ))}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
