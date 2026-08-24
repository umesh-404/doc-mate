"use client";

import { ChevronRight, Search, Users } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { Input } from "@/components/ui/Input";
import { useI18n } from "@/lib/i18n";
import { usePatients } from "@/lib/queries";
import type { Patient } from "@/lib/types";

/**
 * Patient list shared by reception and doctor. Each row links to
 * `${basePath}/${id}` — reception to the upload/verify view, doctor to the
 * snapshot. Data comes from GET /patients with loading/empty/error states.
 */
export function PatientList({ basePath }: { basePath: string }) {
  const { t } = useI18n();
  const [q, setQ] = useState("");
  const { data, isLoading, isError, refetch } = usePatients();

  const filtered = useMemo(() => {
    const list = data ?? [];
    const term = q.trim().toLowerCase();
    if (!term) return list;
    return list.filter(
      (p) =>
        p.full_name.toLowerCase().includes(term) ||
        (p.abha_id ?? "").toLowerCase().includes(term) ||
        p.id.toLowerCase().includes(term),
    );
  }, [data, q]);

  if (isLoading) return <LoadingState label={t.states.loading} />;
  if (isError) {
    return (
      <ErrorState
        title={t.patients.loadError}
        body={t.states.errorBody}
        onRetry={() => void refetch()}
        retryLabel={t.common.retry}
      />
    );
  }

  if ((data ?? []).length === 0) {
    return (
      <EmptyState
        icon={<Users className="h-5 w-5" aria-hidden />}
        title={t.patients.emptyTitle}
        body={t.patients.emptyBody}
      />
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="max-w-md">
        <div className="relative">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted"
            aria-hidden
          />
          <Input
            name="search"
            placeholder={t.patients.searchPlaceholder}
            className="pl-9"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-border bg-surface shadow-card">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse text-sm">
            <thead className="bg-surface-muted/60">
              <tr className="text-left text-xs uppercase tracking-wide text-muted">
                <th className="px-4 py-3 font-medium">{t.patients.colPatient}</th>
                <th className="hidden px-4 py-3 font-medium sm:table-cell">
                  {t.patients.colAbha}
                </th>
                <th className="hidden px-4 py-3 font-medium md:table-cell">
                  {t.patients.colLanguage}
                </th>
                <th className="hidden px-4 py-3 font-medium md:table-cell">
                  {t.patients.colRegistered}
                </th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {filtered.map((p) => (
                <PatientRow key={p.id} patient={p} basePath={basePath} />
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-10 text-center text-muted">
                    {t.patients.noMatch}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function meta(p: Patient): string {
  const bits = [
    p.age != null ? `${p.age}` : null,
    p.sex ?? null,
    p.id,
  ].filter(Boolean);
  return bits.join(" · ");
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function PatientRow({
  patient,
  basePath,
}: {
  patient: Patient;
  basePath: string;
}) {
  const { t } = useI18n();
  const href = `${basePath}/${patient.id}`;
  return (
    <tr className="border-t border-border transition-colors hover:bg-surface-muted/50">
      <td className="px-4 py-3">
        <Link href={href} className="block focus:outline-none focus-visible:underline">
          <span className="font-medium text-foreground">{patient.full_name}</span>
          <span className="block text-xs text-muted">{meta(patient)}</span>
        </Link>
      </td>
      <td className="hidden px-4 py-3 text-muted sm:table-cell">
        {patient.abha_id ?? "—"}
      </td>
      <td className="hidden px-4 py-3 text-muted md:table-cell">
        {patient.preferred_language}
      </td>
      <td className="hidden px-4 py-3 text-muted md:table-cell">
        {formatDate(patient.created_at)}
      </td>
      <td className="px-4 py-3 text-right">
        <Link
          href={href}
          className="inline-flex items-center text-muted hover:text-primary"
          aria-label={`${t.patients.open} ${patient.full_name}`}
        >
          <ChevronRight className="h-4 w-4" />
        </Link>
      </td>
    </tr>
  );
}
