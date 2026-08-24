"use client";

import { FileText } from "lucide-react";
import type { Citation } from "@/lib/mock-data";
import { cn } from "@/lib/utils";

/**
 * Every summary line carries a citation chip back to its source document.
 * Clicking is a no-op stub for now — it will open the source doc/region once
 * the backend document viewer exists. Load-bearing per PROJECT.md §4.3.
 */
export function CitationChip({
  citation,
  className,
}: {
  citation: Citation;
  className?: string;
}) {
  return (
    <button
      type="button"
      title={`Source: ${citation.kind} • ${citation.date} (${citation.documentId})`}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-border bg-surface-muted px-2 py-0.5",
        "text-[11px] font-medium text-muted transition-colors",
        "hover:border-accent/40 hover:bg-primary/5 hover:text-primary",
        className,
      )}
    >
      <FileText className="h-3 w-3" aria-hidden />
      <span>
        {citation.kind} • {citation.date}
      </span>
    </button>
  );
}
