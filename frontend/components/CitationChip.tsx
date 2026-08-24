"use client";

import { FileText } from "lucide-react";
import type { Citation as MockCitation } from "@/lib/mock-data";
import { cn } from "@/lib/utils";

/**
 * Every summary line carries a citation chip back to its source document.
 * Clicking is a no-op stub for now — it will open the source doc/region once
 * the backend document viewer exists. Load-bearing per PROJECT.md §4.3.
 *
 * Accepts either the mock citation shape ({kind, date, documentId}) or the API
 * contract shape via `label` + `documentId`, so it serves both the demo
 * fallback and the real backend-driven snapshot.
 */
type CitationChipProps = {
  className?: string;
} & (
  | { citation: MockCitation; label?: never; documentId?: never }
  | { citation?: never; label: string; documentId: string }
);

export function CitationChip(props: CitationChipProps) {
  const { className } = props;

  const text = props.citation
    ? `${props.citation.kind} • ${props.citation.date}`
    : props.label;
  const documentId = props.citation
    ? props.citation.documentId
    : props.documentId;

  return (
    <button
      type="button"
      title={`Source: ${text} (${documentId})`}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-border bg-surface-muted px-2 py-0.5",
        "text-[11px] font-medium text-muted transition-colors",
        "hover:border-accent/40 hover:bg-primary/5 hover:text-primary",
        className,
      )}
    >
      <FileText className="h-3 w-3" aria-hidden />
      <span>{text}</span>
    </button>
  );
}
