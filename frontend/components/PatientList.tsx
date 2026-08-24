"use client";

import { ChevronRight, Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { StatusBadge } from "@/components/StatusBadge";
import { Input } from "@/components/ui/Input";
import { mockPatients } from "@/lib/mock-data";

/**
 * Patient list shared by reception and doctor. When `basePath` is provided each
 * row links to `${basePath}/${id}` (the doctor snapshot). Reception omits it,
 * so rows are non-navigating. Uses mock data now; a real query against
 * GET /patients drops in here later.
 */
export function PatientList({ basePath }: { basePath?: string }) {
  const [q, setQ] = useState("");

  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase();
    if (!term) return mockPatients;
    return mockPatients.filter(
      (p) =>
        p.name.toLowerCase().includes(term) ||
        p.abhaId.includes(term) ||
        p.id.toLowerCase().includes(term),
    );
  }, [q]);

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
            placeholder="Search by name, ID or ABHA"
            className="pl-9"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-border bg-surface shadow-card">
        <table className="w-full border-collapse text-sm">
          <thead className="bg-surface-muted/60">
            <tr className="text-left text-xs uppercase tracking-wide text-muted">
              <th className="px-4 py-3 font-medium">Patient</th>
              <th className="hidden px-4 py-3 font-medium sm:table-cell">
                Reason for visit
              </th>
              <th className="hidden px-4 py-3 font-medium md:table-cell">
                Last visit
              </th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {filtered.map((p) => (
              <tr
                key={p.id}
                className="border-t border-border transition-colors hover:bg-surface-muted/50"
              >
                <td className="px-4 py-3">
                  {basePath ? (
                    <Link
                      href={`${basePath}/${p.id}`}
                      className="block focus:outline-none"
                    >
                      <span className="font-medium text-foreground">
                        {p.name}
                      </span>
                      <span className="block text-xs text-muted">
                        {p.age} · {p.sex} · {p.id}
                      </span>
                    </Link>
                  ) : (
                    <div>
                      <span className="font-medium text-foreground">
                        {p.name}
                      </span>
                      <span className="block text-xs text-muted">
                        {p.age} · {p.sex} · {p.id}
                      </span>
                    </div>
                  )}
                </td>
                <td className="hidden px-4 py-3 text-muted sm:table-cell">
                  {p.reason}
                </td>
                <td className="hidden px-4 py-3 text-muted md:table-cell">
                  {p.lastVisit}
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={p.status} />
                </td>
                <td className="px-4 py-3 text-right">
                  {basePath && (
                    <Link
                      href={`${basePath}/${p.id}`}
                      className="inline-flex items-center text-muted hover:text-primary"
                      aria-label={`Open ${p.name}`}
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Link>
                  )}
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-muted">
                  No patients match “{q}”.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
