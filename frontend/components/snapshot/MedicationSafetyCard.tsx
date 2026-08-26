"use client";

import { ShieldCheck, ShieldAlert } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Section } from "@/components/ui/Section";
import { useI18n } from "@/lib/i18n";
import type { InteractionReport, InteractionSeverity } from "@/lib/types";

const severityTone: Record<
  InteractionSeverity,
  "danger" | "warning" | "neutral"
> = {
  contraindicated: "danger",
  major: "danger",
  moderate: "warning",
  minor: "neutral",
};

/**
 * Surfaces potential drug–drug interactions and drug–allergy conflicts as
 * verification prompts. Copy is deliberately non-directive: "potential
 * interaction — verify", never "stop this drug". An empty report is shown as a
 * calm reassurance, not a blank space.
 */
export function MedicationSafetyCard({
  report,
}: {
  report: InteractionReport;
}) {
  const { t } = useI18n();
  const hasInteractions = report.interactions.length > 0;
  const hasConflicts = report.allergy_conflicts.length > 0;
  const empty = !hasInteractions && !hasConflicts;

  return (
    <Section
      title={t.snapshot.medSafetyTitle}
      icon={<ShieldAlert className="h-4 w-4" />}
      tone={empty ? "default" : "danger"}
      count={report.interactions.length + report.allergy_conflicts.length}
    >
      {empty ? (
        <div className="flex items-center gap-2 text-sm text-muted">
          <ShieldCheck className="h-4 w-4 text-success" aria-hidden />
          {t.snapshot.medSafetyNone}
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {report.interactions.map((ix, i) => (
            <li
              key={`ix-${i}`}
              className="flex flex-wrap items-start justify-between gap-3 rounded-md border border-danger/30 bg-surface px-3 py-2.5"
            >
              <div className="min-w-0">
                <p className="text-sm font-medium text-foreground">
                  {ix.drug_a} + {ix.drug_b} — {t.snapshot.medSafetyVerify}
                </p>
                <p className="mt-0.5 text-xs text-muted">{ix.description}</p>
                <p className="mt-0.5 text-[11px] text-muted">
                  {t.snapshot.medSafetySource}: {ix.source}
                </p>
              </div>
              <Badge tone={severityTone[ix.severity]}>{ix.severity}</Badge>
            </li>
          ))}
          {report.allergy_conflicts.map((c, i) => (
            <li
              key={`ac-${i}`}
              className="flex flex-wrap items-start justify-between gap-3 rounded-md border border-danger/30 bg-surface px-3 py-2.5"
            >
              <div className="min-w-0">
                <p className="text-sm font-medium text-foreground">
                  {c.medication} ↔ {c.allergen} — {t.snapshot.medSafetyVerify}
                </p>
                <p className="mt-0.5 text-xs text-muted">{c.note}</p>
                <p className="mt-0.5 text-[11px] text-muted">
                  {t.snapshot.medSafetySource}: {c.source}
                </p>
              </div>
              <Badge tone="warning">{t.snapshot.medSafetyAllergy}</Badge>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-[11px] leading-relaxed text-muted">
        {t.snapshot.medSafetyDisclaimer}
      </p>
    </Section>
  );
}
