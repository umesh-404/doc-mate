"use client";

import { BookOpen, Loader2 } from "lucide-react";
import { Section } from "@/components/ui/Section";
import { useI18n } from "@/lib/i18n";
import type { PlainSummary } from "@/lib/types";

/**
 * Readable, patient-friendly narrative of the snapshot (the `/summary/plain`
 * endpoint). Rendered as a calm reading panel with generous line spacing.
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
      title={t.snapshot.plainTitle}
      icon={<BookOpen className="h-4 w-4" />}
    >
      {loading ? (
        <div className="flex items-center gap-2 text-sm text-muted">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          {t.states.loading}
        </div>
      ) : error ? (
        <p className="text-sm text-danger">{t.snapshot.plainError}</p>
      ) : plain ? (
        <p className="whitespace-pre-line text-[15px] leading-7 text-foreground">
          {plain.text}
        </p>
      ) : (
        <p className="text-sm text-muted">{t.snapshot.emptySection}</p>
      )}
    </Section>
  );
}
