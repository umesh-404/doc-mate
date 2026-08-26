"use client";

import { ShieldAlert, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Section } from "@/components/ui/Section";
import { useI18n } from "@/lib/i18n";
import type { InteractionReport, InteractionSeverity } from "@/lib/types";
import { cn } from "@/lib/utils";

const severityTone: Record<
  InteractionSeverity,
  "danger" | "warning" | "neutral"
> = {
  contraindicated: "danger",
  major: "danger",
  moderate: "warning",
  minor: "neutral",
};

const severityRail: Record<InteractionSeverity, string> = {
  contraindicated: "bg-danger",
  major: "bg-danger",
  moderate: "bg-warning",
  minor: "bg-border-strong",
};

const rowClass = cn(
  "avoid-break relative flex flex-wrap items-start justify-between gap-x-3 gap-y-1.5",
  "overflow-hidden rounded-md border border-danger/35 bg-surface py-2.5 pl-4 pr-3",
);

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
      id="snapshot-med-safety"
      title={t.snapshot.medSafetyTitle}
      icon={<ShieldAlert className="h-4 w-4" />}
      tone={empty ? "default" : "danger"}
      count={report.interactions.length + report.allergy_conflicts.length}
    >
      {empty ? (
        <div className="flex items-center gap-2.5 rounded-md border border-success/30 bg-success-surface/60 px-3 py-2.5 text-sm text-foreground-subtle">
          <ShieldCheck className="h-4 w-4 shrink-0 text-success" aria-hidden />
          {t.snapshot.medSafetyNone}
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {report.interactions.map((ix, i) => (
            <li key={`ix-${i}`} className={rowClass}>
              <span
                className={cn(
                  "absolute inset-y-0 left-0 w-1",
                  severityRail[ix.severity],
                )}
                aria-hidden
              />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-foreground text-pretty">
                  <span className="text-danger">{ix.drug_a}</span>
                  {" + "}
                  <span className="text-danger">{ix.drug_b}</span>
                  <span className="font-normal text-foreground-subtle">
                    {" — "}
                    {t.snapshot.medSafetyVerify}
                  </span>
                </p>
                <p className="mt-0.5 text-xs leading-relaxed text-muted">
                  {ix.description}
                </p>
                <p className="mt-1 text-2xs text-muted">
                  {t.snapshot.medSafetySource}: {ix.source}
                </p>
              </div>
              <Badge tone={severityTone[ix.severity]}>{ix.severity}</Badge>
            </li>
          ))}
          {report.allergy_conflicts.map((c, i) => (
            <li key={`ac-${i}`} className={rowClass}>
              <span className="absolute inset-y-0 left-0 w-1 bg-danger" aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-foreground text-pretty">
                  <span className="text-danger">{c.medication}</span>
                  {" ↔ "}
                  <span className="text-danger">{c.allergen}</span>
                  <span className="font-normal text-foreground-subtle">
                    {" — "}
                    {t.snapshot.medSafetyVerify}
                  </span>
                </p>
                <p className="mt-0.5 text-xs leading-relaxed text-muted">
                  {c.note}
                </p>
                <p className="mt-1 text-2xs text-muted">
                  {t.snapshot.medSafetySource}: {c.source}
                </p>
              </div>
              <Badge tone="danger" data-verify-marker>
                {t.snapshot.medSafetyAllergy}
              </Badge>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-2xs leading-relaxed text-muted">
        {t.snapshot.medSafetyDisclaimer}
      </p>
    </Section>
  );
}
