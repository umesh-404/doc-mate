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
  if (trend === "up") return <TrendingUp className="h-4 w-4 text-danger" aria-label="rising" />;
  if (trend === "down")
    return <TrendingDown className="h-4 w-4 text-warning" aria-label="falling" />;
  return <Minus className="h-4 w-4 text-muted" aria-label="stable" />;
}

const flagIcon: Record<Flag["kind"], React.ReactNode> = {
  missing: <Info className="h-4 w-4" aria-hidden />,
  unreadable: <AlertTriangle className="h-4 w-4" aria-hidden />,
  contradiction: <AlertTriangle className="h-4 w-4" aria-hidden />,
};

export function PatientSnapshotView({ data }: { data: PatientSnapshot }) {
  const { t } = useI18n();

  return (
    <div className="flex flex-col gap-5">
      {/* Patient identity header */}
      <div className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-5 shadow-card sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">
              {data.name}
            </h1>
            <Badge tone="neutral">{data.id}</Badge>
          </div>
          <p className="mt-1 text-sm text-muted">
            {data.age} yrs · {data.sex} · Blood group {data.bloodGroup} · ABHA{" "}
            {data.abhaId} · {data.preferredLanguage}
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm text-muted">
          <Clock className="h-4 w-4" aria-hidden />
          {t.snapshot.readTime}
        </div>
      </div>

      {/* Current complaint — top of the read */}
      <Section
        title={t.snapshot.currentComplaint}
        icon={<Stethoscope className="h-4 w-4" />}
      >
        <div className="flex flex-col gap-2">
          <p className="text-[15px] leading-relaxed text-foreground">
            {data.currentComplaint.text}
          </p>
          <div className="flex items-center gap-2">
            <Badge tone="primary">Onset: {data.currentComplaint.onset}</Badge>
            <CitationChip citation={data.currentComplaint.citation} />
          </div>
        </div>
      </Section>

      {/* Allergies — prominent, red. Placed high on purpose. */}
      <Section
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
                className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-danger/30 bg-surface px-3 py-2.5"
              >
                <div className="flex items-center gap-3">
                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-danger-surface text-danger">
                    <AlertTriangle className="h-4 w-4" aria-hidden />
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-foreground">
                      {a.substance}
                    </p>
                    <p className="text-xs text-muted">{a.reaction}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
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

      <div className="grid gap-5 lg:grid-cols-2">
        {/* Active problems */}
        <Section
          title={t.snapshot.activeProblems}
          icon={<HeartPulse className="h-4 w-4" />}
          count={data.problems.length}
        >
          <ul className="flex flex-col divide-y divide-border">
            {data.problems.map((p) => (
              <li
                key={p.label}
                className="flex items-start justify-between gap-3 py-2.5 first:pt-0 last:pb-0"
              >
                <div>
                  <p className="text-sm font-medium text-foreground">{p.label}</p>
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
          title={t.snapshot.medications}
          icon={<Pill className="h-4 w-4" />}
          count={data.medications.length}
        >
          <ul className="flex flex-col divide-y divide-border">
            {data.medications.map((m) => (
              <li
                key={m.name}
                className="flex items-start justify-between gap-3 py-2.5 first:pt-0 last:pb-0"
              >
                <div>
                  <p className="flex items-center gap-2 text-sm font-medium text-foreground">
                    {m.name}
                    {m.needsVerification && (
                      <Badge tone="warning">⚠ verify</Badge>
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
        title={t.snapshot.labs}
        icon={<FlaskConical className="h-4 w-4" />}
        count={data.labs.length}
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px] border-collapse text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-muted">
                <th className="pb-2 pr-4 font-medium">Test</th>
                <th className="pb-2 pr-4 font-medium">Value</th>
                <th className="pb-2 pr-4 font-medium">Reference</th>
                <th className="pb-2 pr-4 font-medium">Trend</th>
                <th className="pb-2 font-medium">Source</th>
              </tr>
            </thead>
            <tbody>
              {data.labs.map((lab: LabResult) => (
                <tr key={lab.name} className="border-t border-border">
                  <td className="py-2.5 pr-4 font-medium text-foreground">
                    {lab.name}
                  </td>
                  <td className="py-2.5 pr-4">
                    <span
                      className={cn(
                        "font-semibold",
                        lab.flag === "high" && "text-danger",
                        lab.flag === "low" && "text-warning",
                        !lab.flag && "text-foreground",
                      )}
                    >
                      {lab.value}
                    </span>{" "}
                    <span className="text-xs text-muted">{lab.unit}</span>
                  </td>
                  <td className="py-2.5 pr-4 text-muted">{lab.reference}</td>
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
        title={t.snapshot.encounters}
        icon={<Clock className="h-4 w-4" />}
        count={data.encounters.length}
      >
        <ol className="relative flex flex-col gap-5 border-l border-border pl-6">
          {data.encounters.map((e) => (
            <li key={`${e.date}-${e.title}`} className="relative">
              <span className="absolute -left-[27px] top-1 h-3 w-3 rounded-full border-2 border-surface bg-primary" />
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-semibold text-foreground">{e.title}</p>
                <CitationChip citation={e.citation} />
              </div>
              <p className="text-xs text-muted">
                {e.date} · {e.facility}
              </p>
              <p className="mt-1 text-sm text-foreground/90">{e.summary}</p>
            </li>
          ))}
        </ol>
      </Section>

      {/* Flags & things to verify */}
      <Section
        title={t.snapshot.flags}
        icon={<AlertTriangle className="h-4 w-4" />}
        tone="danger"
        count={data.flags.length}
      >
        <ul className="flex flex-col gap-2">
          {data.flags.map((f, i) => (
            <li
              key={i}
              className="flex items-start gap-3 rounded-md border border-warning/30 bg-warning-surface/50 px-3 py-2.5"
            >
              <span className="mt-0.5 text-warning" aria-hidden>
                {flagIcon[f.kind]}
              </span>
              <p className="text-sm text-foreground">{f.text}</p>
            </li>
          ))}
        </ul>
      </Section>

      <p className="px-1 pb-4 text-xs leading-relaxed text-muted">
        {t.snapshot.disclaimer}
      </p>
    </div>
  );
}
