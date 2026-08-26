"use client";

import { FileText } from "lucide-react";
import type { Citation as MockCitation } from "@/lib/mock-data";
import { cn } from "@/lib/utils";

/**
 * Every summary line carries a citation chip back to its source document.
 * Clicking is a no-op stub for now — it will open the source doc/region once
 * the backend document viewer exists. Load-bearing per PROJECT.md §4.3: the
 * chip must stay visible and reachable in every theme, and it is deliberately
 * outlined (not filled) in print so it survives a black-and-white handout.
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
      data-citation
      title={`Source: ${text} (${documentId})`}
      aria-label={`Source: ${text}`}
      className={cn(
        "group inline-flex max-w-full items-center gap-1 rounded-full border border-border sm:max-w-[14rem]",
        "bg-surface-muted px-2 py-0.5 text-2xs font-medium text-foreground-subtle",
        "transition-[background-color,border-color,color] duration-150 ease-clinical",
        "hover:border-primary/45 hover:bg-primary/10 hover:text-primary",
        "focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring",
        "active:translate-y-px",
        className,
      )}
    >
      <FileText
        className="h-3 w-3 shrink-0 opacity-70 transition-opacity group-hover:opacity-100"
        aria-hidden
      />
      <span className="truncate">{text}</span>
    </button>
  );
}
