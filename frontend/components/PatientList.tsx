"use client";

import { ChevronRight, Search, Users, X } from "lucide-react";
import Link from "next/link";
import { useMemo, useRef, useState } from "react";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { Input } from "@/components/ui/Input";
import { SkeletonTable } from "@/components/ui/Skeleton";
import { useI18n } from "@/lib/i18n";
import { usePatients } from "@/lib/queries";
import { useShortcuts } from "@/lib/shortcuts";
import type { Patient } from "@/lib/types";

/**
 * Patient list shared by reception and doctor. Each row links to
 * `${basePath}/${id}` — reception to the upload/verify view, doctor to the
 * snapshot. Data comes from GET /patients with loading/empty/error states.
 *
 * The whole row is a link target (a stretched anchor) so it is a large, easy
 * hit area on a small reception screen without nesting interactive elements.
 */
export function PatientList({ basePath }: { basePath: string }) {
  const { t } = useI18n();
  const [q, setQ] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);
  const { data, isLoading, isError, refetch } = usePatients();

  // `/` jumps to search — the fastest way to find a patient mid-consult.
  useShortcuts({
    "/": () => searchRef.current?.focus(),
  });

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

  if (isLoading) return <SkeletonTable label={t.states.loading} />;
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
    <div className="flex animate-fade-in flex-col gap-4">
      <div className="flex max-w-md items-center gap-2">
        <div className="relative flex-1">
          <Input
            ref={searchRef}
            name="search"
            type="search"
            placeholder={t.patients.searchPlaceholder}
            aria-label={t.patients.searchPlaceholder}
            leading={<Search className="h-4 w-4" />}
            className="pr-9"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          {q && (
            <button
              type="button"
              onClick={() => {
                setQ("");
                searchRef.current?.focus();
              }}
              aria-label={t.common.cancel}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-muted transition-colors hover:bg-surface-muted hover:text-foreground"
            >
              <X className="h-3.5 w-3.5" aria-hidden />
            </button>
          )}
        </div>
        <kbd className="kbd hidden sm:inline-flex" aria-hidden>
          /
        </kbd>
      </div>

      <p className="sr-only" aria-live="polite">
        {filtered.length} / {(data ?? []).length}
      </p>

      {/* min-w-0 keeps the wide table scrolling inside its own box instead of
          widening the page on a narrow reception screen. */}
      <div className="min-w-0 overflow-hidden rounded-lg border border-border bg-surface shadow-card">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[620px] border-collapse text-sm">
            <thead className="bg-surface-muted/70">
              <tr className="text-left text-2xs uppercase tracking-[0.08em] text-muted">
                <th scope="col" className="px-4 py-2.5 font-bold">
                  {t.patients.colPatient}
                </th>
                <th
                  scope="col"
                  className="hidden px-4 py-2.5 font-bold sm:table-cell"
                >
                  {t.patients.colAbha}
                </th>
                <th
                  scope="col"
                  className="hidden px-4 py-2.5 font-bold md:table-cell"
                >
                  {t.patients.colLanguage}
                </th>
                <th
                  scope="col"
                  className="hidden px-4 py-2.5 font-bold md:table-cell"
                >
                  {t.patients.colRegistered}
                </th>
                <th scope="col" className="px-4 py-2.5">
                  <span className="sr-only">{t.patients.open}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((p) => (
                <PatientRow key={p.id} patient={p} basePath={basePath} />
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td
                    colSpan={5}
                    className="px-4 py-12 text-center text-sm text-muted"
                  >
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
  const bits = [p.age != null ? `${p.age}` : null, p.sex ?? null, p.id].filter(
    Boolean,
  );
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
  const href = `${basePath}/${patient.id}`;
  return (
    <tr className="group border-t border-border transition-colors hover:bg-surface-muted/60 focus-within:bg-surface-muted/60">
      <td className="relative px-4 py-3">
        {/* Stretched link: the row is one large target, one tab stop. */}
        <Link
          href={href}
          className="after:absolute after:inset-0 after:content-[''] focus:outline-none focus-visible:after:rounded-sm focus-visible:after:outline focus-visible:after:outline-2 focus-visible:after:outline-offset-[-2px] focus-visible:after:outline-ring"
        >
          <span className="font-semibold text-foreground group-hover:text-primary">
            {patient.full_name}
          </span>
          <span className="block text-xs text-muted">{meta(patient)}</span>
        </Link>
      </td>
      <td className="hidden px-4 py-3 font-mono text-xs text-muted sm:table-cell">
        {patient.abha_id ?? "—"}
      </td>
      <td className="hidden px-4 py-3 text-muted md:table-cell">
        {patient.preferred_language}
      </td>
      <td className="hidden px-4 py-3 tabular-nums text-muted md:table-cell">
        {formatDate(patient.created_at)}
      </td>
      <td className="px-4 py-3 text-right">
        <ChevronRight
          className="ml-auto h-4 w-4 text-muted transition-transform duration-150 ease-clinical group-hover:translate-x-0.5 group-hover:text-primary"
          aria-hidden
        />
      </td>
    </tr>
  );
}
