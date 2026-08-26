"use client";

import { AlertOctagon, AlertTriangle, Info } from "lucide-react";
import { CitationChip } from "@/components/CitationChip";
import { useI18n } from "@/lib/i18n";
import type { AlertLevel, SummaryAlert } from "@/lib/types";
import { cn } from "@/lib/utils";

const levelStyle: Record<
  AlertLevel,
  { wrap: string; rail: string; badge: string; icon: React.ReactNode }
> = {
  critical: {
    wrap: "border-danger/45 bg-danger-surface",
    rail: "bg-danger",
    badge: "bg-danger text-danger-foreground",
    icon: <AlertOctagon className="h-4.5 w-4.5" aria-hidden />,
  },
  warning: {
    wrap: "border-warning/45 bg-warning-surface",
    rail: "bg-warning",
    badge: "bg-warning/15 text-warning border border-warning/40",
    icon: <AlertTriangle className="h-4.5 w-4.5" aria-hidden />,
  },
  info: {
    wrap: "border-border bg-surface-muted",
    rail: "bg-border-strong",
    badge: "bg-surface text-muted border border-border",
    icon: <Info className="h-4.5 w-4.5" aria-hidden />,
  },
};

const levelIconTone: Record<AlertLevel, string> = {
  critical: "text-danger",
  warning: "text-warning",
  info: "text-muted",
};

const order: Record<AlertLevel, number> = { critical: 0, warning: 1, info: 2 };

/**
 * The first thing the doctor sees: surfaced alerts (allergies, potential
 * interactions, abnormal labs, missing data), critical first. Every alert is a
 * verification prompt with citation chips — never a directive or a diagnosis.
 *
 * Only `critical` rows animate (a slow halo pulse); that is the one place a
 * moving element is clinically justified, and it is disabled entirely under
 * `prefers-reduced-motion`.
 */
export function AlertsBanner({ alerts }: { alerts: SummaryAlert[] }) {
  const { t } = useI18n();
  if (!alerts || alerts.length === 0) return null;

  const sorted = [...alerts].sort((a, b) => order[a.level] - order[b.level]);
  const criticalCount = sorted.filter((a) => a.level === "critical").length;

  return (
    <section
      id="snapshot-alerts"
      data-section="snapshot-alerts"
      aria-labelledby="snapshot-alerts-heading"
      className="avoid-break scroll-mt-36 flex flex-col gap-2"
    >
      <div className="flex items-center gap-2 px-0.5">
        <h2
          id="snapshot-alerts-heading"
          className={cn(
            "text-2xs font-bold uppercase tracking-[0.09em]",
            criticalCount > 0 ? "text-danger" : "text-muted",
          )}
        >
          {t.snapshot.alertsTitle}
        </h2>
        <span className="rounded-full bg-surface-muted px-1.5 py-px text-2xs font-semibold tabular-nums text-muted">
          {alerts.length}
        </span>
      </div>

      <ul className="flex flex-col gap-2">
        {sorted.map((alert, i) => {
          const s = levelStyle[alert.level];
          return (
            <li
              key={i}
              className={cn(
                "avoid-break relative flex flex-wrap items-start justify-between gap-x-4 gap-y-2",
                "overflow-hidden rounded-lg border py-3 pl-5 pr-4 shadow-card",
                "animate-rise-in",
                s.wrap,
              )}
              style={{ animationDelay: `${Math.min(i, 5) * 45}ms` }}
            >
              {/* Severity rail — readable even with colour vision deficiency
                  because it pairs with a distinct icon and text badge. */}
              <span
                className={cn(
                  "absolute inset-y-0 left-0 w-1.5",
                  s.rail,
                  alert.level === "critical" && "animate-rail-pulse",
                )}
                aria-hidden
              />
              <div className="flex min-w-0 flex-1 items-start gap-2.5">
                <span
                  className={cn("mt-px shrink-0", levelIconTone[alert.level])}
                >
                  {s.icon}
                </span>
                <div className="min-w-0">
                  <span
                    className={cn(
                      "mb-1 inline-block rounded px-1.5 py-px text-[10px] font-bold uppercase tracking-[0.08em]",
                      s.badge,
                    )}
                  >
                    {alert.level}
                  </span>
                  <p className="text-md font-semibold leading-snug text-foreground text-pretty">
                    {alert.text}
                  </p>
                </div>
              </div>
              {alert.citations.length > 0 && (
                <div className="flex max-w-full flex-wrap items-center gap-1.5 pl-7 sm:pl-0">
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
    </section>
  );
}
