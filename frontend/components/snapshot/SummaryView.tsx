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
import { PatientIdentityBar } from "@/components/snapshot/PatientIdentityBar";
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
import { MedicationSafetyCard } from "./MedicationSafetyCard";
import { Sparkline, extractSeries } from "./Sparkline";

/** Icon + framing per section key. Allergies and flags are framed red. */
const sectionMeta: Record<
  SectionKey,
  { icon: React.ReactNode; tone: "default" | "danger" | "warning" }
> = {
  complaint: { icon: <Stethoscope className="h-4 w-4" />, tone: "default" },
  problems: { icon: <HeartPulse className="h-4 w-4" />, tone: "default" },
  allergies: { icon: <ShieldAlert className="h-4 w-4" />, tone: "danger" },
  medications: { icon: <Pill className="h-4 w-4" />, tone: "default" },
  labs: { icon: <FlaskConical className="h-4 w-4" />, tone: "default" },
  encounters: { icon: <Clock className="h-4 w-4" />, tone: "default" },
  flags: { icon: <AlertTriangle className="h-4 w-4" />, tone: "warning" },
};

/** Sections that read best side-by-side on a wide screen. */
const PAIRED: SectionKey[] = ["problems", "medications"];

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
          className={cn(
            "inline-flex items-center gap-1 rounded border border-border-strong/60 bg-surface-muted",
            "px-1.5 py-px font-mono text-[10px] font-semibold uppercase tracking-tight text-muted",
          )}
        >
          <span className="opacity-70">{c.system}</span>
          <span className="text-foreground-subtle">{c.code}</span>
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
  index,
}: {
  item: SummaryItem;
  tone: "default" | "danger" | "warning";
  codes: MedicalCode[];
  showSparkline?: boolean;
  index: number;
}) {
  const { t } = useI18n();
  const needsVerify = item.verified === false;
  const ungrounded = item.grounded === false;
  const series = showSparkline ? extractSeries(item.text) : [];
  const flagged = needsVerify || ungrounded;

  return (
    <li
      className={cn(
        "avoid-break group flex flex-wrap items-start justify-between gap-x-3 gap-y-2",
        "rounded-md border px-3 py-2.5 animate-rise-in",
        "transition-colors duration-150 ease-clinical",
        tone === "danger"
          ? "border-danger/35 bg-surface hover:border-danger/55"
          : flagged
            ? "border-warning/40 bg-warning-surface/25 hover:border-warning/60"
            : "border-border bg-surface hover:border-border-strong",
      )}
      style={{ animationDelay: `${Math.min(index, 8) * 30}ms` }}
    >
      <div className="flex min-w-0 flex-1 items-start gap-2">
        {item.trend && (
          <span className="mt-0.5 shrink-0" aria-hidden>
            <TrendIcon trend={item.trend} />
          </span>
        )}
        <div className="min-w-0">
          <p className="text-sm leading-relaxed text-foreground text-pretty">
            {item.text}
          </p>
          {series.length >= 2 && (
            <span className="mt-1.5 inline-block">
              <Sparkline values={series} label={item.text} />
            </span>
          )}
        </div>
      </div>

      <div className="flex max-w-full flex-wrap items-center gap-1.5 sm:justify-end">
        <CodeChips codes={codes} />
        {item.severity && (
          <Badge tone={severityTone[item.severity]}>{item.severity}</Badge>
        )}
        {/* Ungrounded marker — must stay visible, never softened away. */}
        {ungrounded && (
          <span
            data-verify-marker
            title={item.grounding_note ?? t.snapshot.ungroundedTip}
            className={cn(
              "inline-flex items-center gap-1 rounded-full border border-warning/45 bg-warning-surface",
              "px-2 py-0.5 text-2xs font-semibold text-warning",
            )}
          >
            <ShieldQuestion className="h-3 w-3 shrink-0" aria-hidden />
            {t.snapshot.unverifiedBySource}
          </span>
        )}
        {needsVerify && (
          <Badge tone="warning" data-verify-marker>
            {t.snapshot.needsVerify}
          </Badge>
        )}
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
      id="snapshot-encounters"
      title={section.title}
      icon={meta.icon}
      tone={meta.tone}
      count={section.items.length}
    >
      {section.items.length === 0 ? (
        <p className="text-sm text-muted">{t.snapshot.emptySection}</p>
      ) : (
        <ol className="relative flex flex-col gap-4 pl-6">
          {/* The rail fades out at the bottom so the timeline reads as
              "most recent first, history trailing off". */}
          <span
            className="absolute inset-y-1 left-[5px] w-px bg-gradient-to-b from-border-strong via-border to-transparent"
            aria-hidden
          />
          {section.items.map((item, i) => (
            <li
              key={i}
              className="avoid-break relative animate-rise-in"
              style={{ animationDelay: `${Math.min(i, 8) * 40}ms` }}
            >
              <span
                className={cn(
                  "absolute -left-6 top-1 h-[11px] w-[11px] rounded-full border-2 border-surface",
                  i === 0 ? "bg-primary ring-2 ring-primary/25" : "bg-border-strong",
                )}
                aria-hidden
              />
              <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1.5">
                <p
                  className={cn(
                    "min-w-0 flex-1 text-sm leading-relaxed text-pretty",
                    i === 0
                      ? "font-medium text-foreground"
                      : "text-foreground-subtle",
                  )}
                >
                  {item.text}
                </p>
                <div className="flex max-w-full flex-wrap items-center gap-1.5">
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
      id={`snapshot-${section.key}`}
      title={section.title}
      icon={meta.icon}
      tone={meta.tone}
      count={section.items.length}
      className="h-full"
    >
      {section.items.length === 0 ? (
        <p className="text-sm text-muted">{t.snapshot.emptySection}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {section.items.map((item, i) => (
            <ItemRow
              key={i}
              index={i}
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
 * up top, a sticky identity + grounding bar, per-item source-grounding markers,
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

  // Group the two-column pair so `problems` and `medications` sit side by side
  // on wide screens without disturbing the backend's section order.
  const rendered: React.ReactNode[] = [];
  const sections = summary.sections;
  for (let i = 0; i < sections.length; i += 1) {
    const section = sections[i]!;
    const next = sections[i + 1];
    if (
      next &&
      PAIRED.includes(section.key) &&
      PAIRED.includes(next.key) &&
      section.key !== next.key
    ) {
      rendered.push(
        <div
          key={`${section.key}-pair`}
          className="grid grid-cols-1 gap-4 lg:grid-cols-2"
        >
          <SectionBlock section={section} codeIndex={codeIndex} />
          <SectionBlock section={next} codeIndex={codeIndex} />
        </div>,
      );
      i += 1;
      continue;
    }
    rendered.push(
      section.key === "encounters" ? (
        <EncounterTimeline key={section.key} section={section} />
      ) : (
        <SectionBlock
          key={section.key}
          section={section}
          codeIndex={codeIndex}
        />
      ),
    );
  }

  return (
    <article className="flex flex-col gap-4">
      <PatientIdentityBar
        identity={{
          name: patient.full_name,
          id: patient.id,
          meta: patientMeta(patient),
        }}
        grounding={summary.grounding}
      />

      {/* Critical-alerts banner — first thing the doctor reads */}
      {summary.alerts && summary.alerts.length > 0 && (
        <AlertsBanner alerts={summary.alerts} />
      )}

      {rendered}

      {/* Medication safety — interactions + allergy conflicts */}
      {interactions && <MedicationSafetyCard report={interactions} />}

      <p className="mt-1 rounded-md border border-dashed border-border bg-surface-muted/40 px-3.5 py-2.5 text-xs leading-relaxed text-muted">
        {t.snapshot.disclaimer}
      </p>
    </article>
  );
}
