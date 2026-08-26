"use client";

import {
  AlertTriangle,
  Clock,
  FlaskConical,
  HeartPulse,
  Info,
  Minus,
  Pill,
  ShieldAlert,
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
  Flag,
  LabResult,
  PatientSnapshot,
  Severity,
  TrendDirection,
} from "@/lib/mock-data";
import { cn } from "@/lib/utils";

const severityTone: Record<Severity, "danger" | "warning" | "neutral"> = {
  high: "danger",
  moderate: "warning",
  low: "neutral",
};

function TrendIcon({ trend }: { trend: TrendDirection }) {
  if (trend === "up")
    return <TrendingUp className="h-4 w-4 text-danger" aria-label="rising" />;
  if (trend === "down")
    return <TrendingDown className="h-4 w-4 text-warning" aria-label="falling" />;
  return <Minus className="h-4 w-4 text-muted" aria-label="stable" />;
}

const flagIcon: Record<Flag["kind"], React.ReactNode> = {
  missing: <Info className="h-4 w-4" aria-hidden />,
  unreadable: <AlertTriangle className="h-4 w-4" aria-hidden />,
  contradiction: <AlertTriangle className="h-4 w-4" aria-hidden />,
};

const rowClass =
  "flex flex-wrap items-start justify-between gap-x-3 gap-y-1.5 py-2.5 first:pt-0 last:pb-0";

/**
 * Sample snapshot rendered from bundled demo data. Visually identical to the
 * live SummaryView so a judge sees the same craft even before a summary has
 * been generated — the caller is responsible for labelling it as a sample.
 */
export function PatientSnapshotView({ data }: { data: PatientSnapshot }) {
  const { t } = useI18n();

  return (
    <article className="flex flex-col gap-4">
      <PatientIdentityBar
        identity={{
          name: data.name,
          id: data.id,
          meta: `${data.age} yrs · ${data.sex} · Blood group ${data.bloodGroup} · ABHA ${data.abhaId} · ${data.preferredLanguage}`,
        }}
      />

      {/* Current complaint — top of the read */}
      <Section
        id="snapshot-complaint"
        title={t.snapshot.currentComplaint}
        icon={<Stethoscope className="h-4 w-4" />}
      >
        <div className="flex flex-col gap-2.5">
          <p className="max-w-[70ch] text-md leading-relaxed text-foreground text-pretty">
            {data.currentComplaint.text}
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="primary">Onset: {data.currentComplaint.onset}</Badge>
            <CitationChip citation={data.currentComplaint.citation} />
          </div>
        </div>
      </Section>

      {/* Allergies — prominent, red. Placed high on purpose. */}
      <Section
        id="snapshot-allergies"
        title={t.snapshot.allergies}
        icon={<ShieldAlert className="h-4 w-4" />}
        tone="danger"
        count={data.allergies.length}
      >
        {data.allergies.length === 0 ? (
          <p className="text-sm text-muted">{t.snapshot.noAllergies}</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {data.allergies.map((a) => (
              <li
                key={a.substance}
                className="avoid-break flex flex-wrap items-center justify-between gap-x-3 gap-y-2 rounded-md border border-danger/40 bg-surface px-3 py-2.5"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-danger/30 bg-danger-surface text-danger">
                    <AlertTriangle className="h-4 w-4" aria-hidden />
                  </span>
                  <div className="min-w-0">
                    <p className="text-md font-semibold text-danger">
                      {a.substance}
                    </p>
                    <p className="text-xs text-muted">{a.reaction}</p>
                  </div>
                </div>
                <div className="flex max-w-full flex-wrap items-center gap-2">
                  <Badge tone={severityTone[a.severity]}>
                    {a.severity} severity
                  </Badge>
                  <CitationChip citation={a.citation} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Active problems */}
        <Section
          id="snapshot-problems"
          title={t.snapshot.activeProblems}
          icon={<HeartPulse className="h-4 w-4" />}
          count={data.problems.length}
          className="h-full"
        >
          <ul className="flex flex-col divide-y divide-border">
            {data.problems.map((p) => (
              <li key={p.label} className={rowClass}>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-foreground">
                    {p.label}
                  </p>
                  <p className="text-xs text-muted">
                    {p.detail} · since {p.since}
                  </p>
                </div>
                <CitationChip citation={p.citation} />
              </li>
            ))}
          </ul>
        </Section>

        {/* Current medications */}
        <Section
          id="snapshot-medications"
          title={t.snapshot.medications}
          icon={<Pill className="h-4 w-4" />}
          count={data.medications.length}
          className="h-full"
        >
          <ul className="flex flex-col divide-y divide-border">
            {data.medications.map((m) => (
              <li key={m.name} className={rowClass}>
                <div className="min-w-0">
                  <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-foreground">
                    {m.name}
                    {m.needsVerification && (
                      <Badge tone="warning" data-verify-marker>
                        ⚠ verify
                      </Badge>
                    )}
                  </p>
                  <p className="text-xs text-muted">
                    {m.dose} · {m.frequency} · since {m.since}
                  </p>
                </div>
                <CitationChip citation={m.citation} />
              </li>
            ))}
          </ul>
        </Section>
      </div>

      {/* Recent labs & trends */}
      <Section
        id="snapshot-labs"
        title={t.snapshot.labs}
        icon={<FlaskConical className="h-4 w-4" />}
        count={data.labs.length}
      >
        <div className="-mx-1 overflow-x-auto px-1">
          <table className="w-full min-w-[520px] border-collapse text-sm">
            <caption className="sr-only">{t.snapshot.labs}</caption>
            <thead>
              <tr className="text-left text-2xs uppercase tracking-[0.08em] text-muted">
                <th scope="col" className="pb-2 pr-4 font-semibold">
                  Test
                </th>
                <th scope="col" className="pb-2 pr-4 font-semibold">
                  Value
                </th>
                <th scope="col" className="pb-2 pr-4 font-semibold">
                  Reference
                </th>
                <th scope="col" className="pb-2 pr-4 font-semibold">
                  Trend
                </th>
                <th scope="col" className="pb-2 font-semibold">
                  Source
                </th>
              </tr>
            </thead>
            <tbody>
              {data.labs.map((lab: LabResult) => (
                <tr
                  key={lab.name}
                  className="border-t border-border transition-colors hover:bg-surface-muted/50"
                >
                  <th
                    scope="row"
                    className="py-2.5 pr-4 text-left font-medium text-foreground"
                  >
                    {lab.name}
                  </th>
                  <td className="py-2.5 pr-4 tabular-nums">
                    <span
                      className={cn(
                        "text-md font-bold",
                        lab.flag === "high" && "text-danger",
                        lab.flag === "low" && "text-warning",
                        !lab.flag && "text-foreground",
                      )}
                    >
                      {lab.value}
                    </span>{" "}
                    <span className="text-xs text-muted">{lab.unit}</span>
                  </td>
                  <td className="py-2.5 pr-4 tabular-nums text-muted">
                    {lab.reference}
                  </td>
                  <td className="py-2.5 pr-4">
                    <TrendIcon trend={lab.trend} />
                  </td>
                  <td className="py-2.5">
                    <CitationChip citation={lab.citation} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {/* Past encounters timeline */}
      <Section
        id="snapshot-encounters"
        title={t.snapshot.encounters}
        icon={<Clock className="h-4 w-4" />}
        count={data.encounters.length}
      >
        <ol className="relative flex flex-col gap-4 pl-6">
          <span
            className="absolute inset-y-1 left-[5px] w-px bg-gradient-to-b from-border-strong via-border to-transparent"
            aria-hidden
          />
          {data.encounters.map((e, i) => (
            <li key={`${e.date}-${e.title}`} className="avoid-break relative">
              <span
                className={cn(
                  "absolute -left-6 top-1 h-[11px] w-[11px] rounded-full border-2 border-surface",
                  i === 0
                    ? "bg-primary ring-2 ring-primary/25"
                    : "bg-border-strong",
                )}
                aria-hidden
              />
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <p className="text-sm font-semibold text-foreground">
                  {e.title}
                </p>
                <CitationChip citation={e.citation} />
              </div>
              <p className="text-xs text-muted">
                {e.date} · {e.facility}
              </p>
              <p className="mt-1 text-sm leading-relaxed text-foreground-subtle text-pretty">
                {e.summary}
              </p>
            </li>
          ))}
        </ol>
      </Section>

      {/* Flags & things to verify */}
      <Section
        id="snapshot-flags"
        title={t.snapshot.flags}
        icon={<AlertTriangle className="h-4 w-4" />}
        tone="warning"
        count={data.flags.length}
      >
        <ul className="flex flex-col gap-2">
          {data.flags.map((f, i) => (
            <li
              key={i}
              data-verify-marker
              className="avoid-break flex items-start gap-2.5 rounded-md border border-warning/45 bg-warning-surface/60 px-3 py-2.5"
            >
              <span className="mt-0.5 shrink-0 text-warning" aria-hidden>
                {flagIcon[f.kind]}
              </span>
              <p className="text-sm leading-relaxed text-foreground text-pretty">
                {f.text}
              </p>
            </li>
          ))}
        </ul>
      </Section>

      <p className="mt-1 rounded-md border border-dashed border-border bg-surface-muted/40 px-3.5 py-2.5 text-xs leading-relaxed text-muted">
        {t.snapshot.disclaimer}
      </p>
    </article>
  );
}
