"use client";

import {
  AlertTriangle,
  Clock,
  FlaskConical,
  HeartPulse,
  Minus,
  Pill,
  ShieldAlert,
  ShieldQuestion,
  Stethoscope,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { CitationChip } from "@/components/CitationChip";
import { Badge } from "@/components/ui/Badge";
import { Section } from "@/components/ui/Section";
import { useI18n } from "@/lib/i18n";
import type {
  InteractionReport,
  ItemCodes,
  MedicalCode,
  Patient,
  SectionKey,
  Summary,
  SummaryItem,
  SummarySection,
  SummarySeverity,
  SummaryTrend,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import { AlertsBanner } from "./AlertsBanner";
import { GroundingBadge } from "./GroundingBadge";
import { MedicationSafetyCard } from "./MedicationSafetyCard";
import { Sparkline, extractSeries } from "./Sparkline";

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

/** Small muted chips for the ICD-11 / NAMASTE codes mapped to an item. */
function CodeChips({ codes }: { codes: MedicalCode[] }) {
  if (codes.length === 0) return null;
  return (
    <>
      {codes.map((c, i) => (
        <span
          key={`${c.system}-${c.code}-${i}`}
          title={`${c.system} ${c.code} — ${c.display}`}
          className="inline-flex items-center gap-1 rounded-full border border-border bg-surface-muted px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted"
        >
          {c.system} {c.code}
        </span>
      ))}
    </>
  );
}

/** Match an item's text to a coded clinical concept by label overlap. */
function codesFor(text: string, codeIndex: ItemCodes[]): MedicalCode[] {
  const lower = text.toLowerCase();
  const hit = codeIndex.find(
    (c) => c.item_label && lower.includes(c.item_label.toLowerCase()),
  );
  return hit?.codes ?? [];
}

function ItemRow({
  item,
  tone,
  codes,
  showSparkline,
}: {
  item: SummaryItem;
  tone: "default" | "danger";
  codes: MedicalCode[];
  showSparkline?: boolean;
}) {
  const { t } = useI18n();
  const needsVerify = item.verified === false;
  const ungrounded = item.grounded === false;
  const series = showSparkline ? extractSeries(item.text) : [];

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
        <div className="min-w-0">
          <p className="text-sm leading-relaxed text-foreground">{item.text}</p>
          {series.length >= 2 && (
            <span className="mt-1 inline-block">
              <Sparkline values={series} />
            </span>
          )}
        </div>
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-1.5">
        <CodeChips codes={codes} />
        {item.severity && (
          <Badge tone={severityTone[item.severity]}>{item.severity}</Badge>
        )}
        {ungrounded && (
          <span
            title={item.grounding_note ?? t.snapshot.ungroundedTip}
            className="inline-flex items-center gap-1 rounded-full border border-border bg-surface-muted px-2 py-0.5 text-[11px] font-medium text-muted"
          >
            <ShieldQuestion className="h-3 w-3" aria-hidden />
            {t.snapshot.unverifiedBySource}
          </span>
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

/** Encounters render as a clean vertical timeline instead of plain rows. */
function EncounterTimeline({ section }: { section: SummarySection }) {
  const { t } = useI18n();
  const meta = sectionMeta.encounters;
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
        <ol className="relative flex flex-col gap-5 border-l border-border pl-6">
          {section.items.map((item, i) => (
            <li key={i} className="relative">
              <span className="absolute -left-[27px] top-1 h-3 w-3 rounded-full border-2 border-surface bg-primary" />
              <div className="flex flex-wrap items-start justify-between gap-2">
                <p className="text-sm text-foreground">{item.text}</p>
                <div className="flex shrink-0 flex-wrap items-center gap-1.5">
                  {item.citations.map((c, ci) => (
                    <CitationChip
                      key={`${c.document_id}-${ci}`}
                      label={c.label}
                      documentId={c.document_id}
                    />
                  ))}
                </div>
              </div>
            </li>
          ))}
        </ol>
      )}
    </Section>
  );
}

function SectionBlock({
  section,
  codeIndex,
}: {
  section: SummarySection;
  codeIndex: ItemCodes[];
}) {
  const { t } = useI18n();
  const meta = sectionMeta[section.key] ?? sectionMeta.problems;
  const isLabs = section.key === "labs";
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
            <ItemRow
              key={i}
              item={item}
              tone={meta.tone}
              codes={codesFor(item.text, codeIndex)}
              showSparkline={isLabs}
            />
          ))}
        </ul>
      )}
    </Section>
  );
}

/**
 * Renders the backend-generated Summary (contract v2): a critical-alerts banner
 * up top, a grounding badge on the header, per-item source-grounding markers,
 * ICD-11/NAMASTE code chips, inline lab sparklines, an encounter timeline and a
 * medication-safety card. Keeps the "surfaces and cites — does not diagnose"
 * framing throughout.
 */
export function SummaryView({
  summary,
  patient,
  codes,
  interactions,
}: {
  summary: Summary;
  patient: Patient;
  codes?: ItemCodes[] | null;
  interactions?: InteractionReport | null;
}) {
  const { t } = useI18n();
  const codeIndex = codes ?? [];

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
        <div className="flex flex-col items-start gap-2 sm:items-end">
          {summary.grounding && <GroundingBadge grounding={summary.grounding} />}
          <div className="flex items-center gap-2 text-sm text-muted">
            <Clock className="h-4 w-4" aria-hidden />
            {t.snapshot.readTime}
          </div>
        </div>
      </div>

      {/* Critical-alerts banner — first thing the doctor reads */}
      {summary.alerts && summary.alerts.length > 0 && (
        <AlertsBanner alerts={summary.alerts} />
      )}

      {summary.sections.map((section) =>
        section.key === "encounters" ? (
          <EncounterTimeline key={section.key} section={section} />
        ) : (
          <SectionBlock
            key={section.key}
            section={section}
            codeIndex={codeIndex}
          />
        ),
      )}

      {/* Medication safety — interactions + allergy conflicts */}
      {interactions && <MedicationSafetyCard report={interactions} />}

      <p className="px-1 pb-4 text-xs leading-relaxed text-muted">
        {t.snapshot.disclaimer}
      </p>
    </div>
  );
}
