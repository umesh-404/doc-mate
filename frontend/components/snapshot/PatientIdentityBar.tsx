"use client";

import { Clock } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { GroundingBadge } from "@/components/snapshot/GroundingBadge";
import { Badge } from "@/components/ui/Badge";
import { useI18n } from "@/lib/i18n";
import type { Grounding } from "@/lib/types";
import { cn } from "@/lib/utils";

export type IdentityFields = {
  name: string;
  id: string;
  meta: string;
};

/**
 * Patient identity for the snapshot, in two coordinated pieces:
 *
 *  1. A full header card at the top of the read.
 *  2. A compact sticky bar that slides in once that card scrolls away, so the
 *     doctor never loses track of *whose* record they are reading — the single
 *     most dangerous thing to lose in a five-minute, high-throughput clinic.
 *
 * The sticky bar carries the grounding badge too, so the trust signal stays on
 * screen alongside the name.
 */
export function PatientIdentityBar({
  identity,
  grounding,
}: {
  identity: IdentityFields;
  grounding?: Grounding | null;
}) {
  const { t } = useI18n();
  const sentinelRef = useRef<HTMLDivElement>(null);
  const [stuck, setStuck] = useState(false);

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      ([entry]) => setStuck(!entry?.isIntersecting),
      // Fire once the header card passes under the app header (56px) + margin.
      { rootMargin: "-72px 0px 0px 0px", threshold: 0 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <>
      {/* Full identity header */}
      <div
        ref={sentinelRef}
        className="avoid-break flex animate-rise-in flex-col gap-3 rounded-lg border border-border bg-surface p-4 shadow-card sm:flex-row sm:items-center sm:justify-between sm:p-5"
      >
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">
              {identity.name}
            </h1>
            <Badge tone="outline" className="font-mono">
              {identity.id}
            </Badge>
          </div>
          <p className="mt-1 text-sm text-muted text-pretty">{identity.meta}</p>
        </div>
        <div className="flex shrink-0 flex-row-reverse items-center justify-end gap-3 sm:flex-col sm:items-end sm:gap-2">
          {grounding && <GroundingBadge grounding={grounding} />}
          <span className="inline-flex items-center gap-1.5 text-xs text-muted">
            <Clock className="h-3.5 w-3.5" aria-hidden />
            {t.snapshot.readTime}
          </span>
        </div>
      </div>

      {/* Compact sticky context bar */}
      <div
        aria-hidden={!stuck}
        className={cn(
          "pointer-events-none fixed inset-x-0 top-14 z-20 print:hidden",
          "transition-[opacity,transform] duration-200 ease-clinical",
          stuck
            ? "translate-y-0 opacity-100"
            : "-translate-y-2 opacity-0",
        )}
      >
        <div className="mx-auto max-w-6xl px-4">
          <div
            className={cn(
              "pointer-events-auto flex items-center justify-between gap-3 rounded-b-lg border border-t-0",
              "border-border bg-surface/95 px-4 py-2 shadow-card-lg backdrop-blur-md",
            )}
          >
            <div className="flex min-w-0 items-baseline gap-2">
              <span className="truncate text-sm font-semibold text-foreground">
                {identity.name}
              </span>
              <span className="hidden truncate text-xs text-muted sm:inline">
                {identity.meta}
              </span>
            </div>
            {grounding && <GroundingBadge grounding={grounding} compact />}
          </div>
        </div>
      </div>
    </>
  );
}
