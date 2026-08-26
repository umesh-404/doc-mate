"use client";

import { BookOpen, Loader2 } from "lucide-react";
import { Section } from "@/components/ui/Section";
import { Skeleton } from "@/components/ui/Skeleton";
import { useI18n } from "@/lib/i18n";
import type { PlainSummary } from "@/lib/types";

/**
 * Readable, patient-friendly narrative of the snapshot (the `/summary/plain`
 * endpoint). Rendered as a calm reading panel: narrower measure and generous
 * leading so it reads like prose rather than another data table.
 */
export function PlainLanguagePanel({
  plain,
  loading,
  error,
}: {
  plain: PlainSummary | null | undefined;
  loading: boolean;
  error: boolean;
}) {
  const { t } = useI18n();

  return (
    <Section
      id="snapshot-plain"
      title={t.snapshot.plainTitle}
      icon={<BookOpen className="h-4 w-4" />}
      className="animate-expand-down"
    >
      <div aria-live="polite" aria-busy={loading}>
        {loading ? (
          <div className="flex flex-col gap-2.5">
            <span className="sr-only">
              <Loader2 className="h-4 w-4" aria-hidden />
              {t.states.loading}
            </span>
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-[92%]" />
            <Skeleton className="h-4 w-[97%]" />
            <Skeleton className="h-4 w-[60%]" />
          </div>
        ) : error ? (
          <p role="alert" className="text-sm font-medium text-danger">
            {t.snapshot.plainError}
          </p>
        ) : plain ? (
          <p className="max-w-[68ch] whitespace-pre-line text-md leading-7 text-foreground-subtle">
            {plain.text}
          </p>
        ) : (
          <p className="text-sm text-muted">{t.snapshot.emptySection}</p>
        )}
      </div>
    </Section>
  );
}
