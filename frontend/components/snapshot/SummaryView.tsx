"use client";

import {
  AlertTriangle,
  Clock,
  FlaskConical,
  HeartPulse,
  Minus,
  Pill,
  ShieldAlert,
  Stethoscope,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { CitationChip } from "@/components/CitationChip";
import { Badge } from "@/components/ui/Badge";
import { Section } from "@/components/ui/Section";
import { useI18n } from "@/lib/i18n";
import type {
  Patient,
  SectionKey,
  Summary,
  SummaryItem,
  SummarySection,
  SummarySeverity,
  SummaryTrend,
} from "@/lib/types";
import { cn } from "@/lib/utils";

/** Icon + framing per section key. Allergies and flags are framed red. */
const sectionMeta: Record<
  SectionKey,
  { icon: React.ReactNode; tone: "default" | "danger" }
> = {
  complaint: { icon: <Stethoscope className="h-4 w-4" />, tone: "default" },
  problems: { icon: <HeartPulse className="h-4 w-4" />, tone: "default" },
  allergies: { icon: <ShieldAlert className="h-4 w-4" />, tone: "danger" },
  medications: { icon: <Pill className="h-4 w-4" />, tone: "default" },
  labs: { icon: <FlaskConical className="h-4 w-4" />, tone: "default" },
  encounters: { icon: <Clock className="h-4 w-4" />, tone: "default" },
  flags: { icon: <AlertTriangle className="h-4 w-4" />, tone: "danger" },
};

const severityTone: Record<SummarySeverity, "danger" | "warning" | "neutral"> = {
  high: "danger",
  med: "warning",
  low: "neutral",
};

function TrendIcon({ trend }: { trend: SummaryTrend }) {
  if (trend === "up")
    return <TrendingUp className="h-4 w-4 text-danger" aria-label="rising" />;
  if (trend === "down")
    return <TrendingDown className="h-4 w-4 text-warning" aria-label="falling" />;
  return <Minus className="h-4 w-4 text-muted" aria-label="flat" />;
}

function patientMeta(p: Patient): string {
  return [
    p.age != null ? `${p.age} yrs` : null,
    p.sex,
    p.abha_id ? `ABHA ${p.abha_id}` : null,
    p.preferred_language,
  ]
    .filter(Boolean)
    .join(" · ");
}

function ItemRow({
  item,
  tone,
}: {
  item: SummaryItem;
  tone: "default" | "danger";
}) {
  const { t } = useI18n();
  const needsVerify = item.verified === false;

  return (
    <li
      className={cn(
        "flex flex-wrap items-start justify-between gap-3 rounded-md border px-3 py-2.5",
        tone === "danger"
          ? "border-danger/30 bg-surface"
          : "border-border bg-surface",
      )}
    >
      <div className="flex min-w-0 items-start gap-2">
        {item.trend && (
          <span className="mt-0.5 shrink-0" aria-hidden>
            <TrendIcon trend={item.trend} />
          </span>
        )}
        <p className="text-sm leading-relaxed text-foreground">{item.text}</p>
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-1.5">
        {item.severity && (
          <Badge tone={severityTone[item.severity]}>{item.severity}</Badge>
        )}
        {needsVerify && <Badge tone="warning">{t.snapshot.needsVerify}</Badge>}
        {item.citations.map((c, i) => (
          <CitationChip
            key={`${c.document_id}-${i}`}
            label={c.label}
            documentId={c.document_id}
          />
        ))}
      </div>
    </li>
  );
}

function SectionBlock({ section }: { section: SummarySection }) {
  const { t } = useI18n();
  const meta = sectionMeta[section.key] ?? sectionMeta.problems;
  return (
    <Section
      title={section.title}
      icon={meta.icon}
      tone={meta.tone}
      count={section.items.length}
    >
      {section.items.length === 0 ? (
        <p className="text-sm text-muted">{t.snapshot.emptySection}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {section.items.map((item, i) => (
            <ItemRow key={i} item={item} tone={meta.tone} />
          ))}
        </ul>
      )}
    </Section>
  );
}

/**
 * Renders the real backend-generated Summary (contract v1) using the same
 * visual language as the demo snapshot: allergies/flags framed red, meds & other
 * low-confidence items flagged ⚠ verify, lab trend arrows, citation chips, a
 * read-time estimate and the "summarises, never diagnoses" disclaimer.
 */
export function SummaryView({
  summary,
  patient,
}: {
  summary: Summary;
  patient: Patient;
}) {
  const { t } = useI18n();

  return (
    <div className="flex flex-col gap-5">
      {/* Patient identity header */}
      <div className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-5 shadow-card sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">
              {patient.full_name}
            </h1>
            <Badge tone="neutral">{patient.id}</Badge>
          </div>
          <p className="mt-1 text-sm text-muted">{patientMeta(patient)}</p>
        </div>
        <div className="flex items-center gap-2 text-sm text-muted">
          <Clock className="h-4 w-4" aria-hidden />
          {t.snapshot.readTime}
        </div>
      </div>

      {summary.sections.map((section) => (
        <SectionBlock key={section.key} section={section} />
      ))}

      <p className="px-1 pb-4 text-xs leading-relaxed text-muted">
        {t.snapshot.disclaimer}
      </p>
    </div>
  );
}
