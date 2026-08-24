"use client";

import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  FileText,
  Loader2,
} from "lucide-react";
import { useMemo, useState } from "react";
import { StatusBadge } from "@/components/StatusBadge";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useI18n } from "@/lib/i18n";
import { useDocument, useVerifyDocument } from "@/lib/queries";
import {
  CLINICAL_KIND_LABEL,
  DOC_TYPES,
  LOW_CONFIDENCE,
  type ClinicalItem,
  type DocumentStatus,
  type DocumentSummary,
} from "@/lib/types";
import type { Dictionary } from "@/lib/i18n/dictionaries";
import { cn } from "@/lib/utils";

const DOC_TYPE_LABEL_KEYS = Object.fromEntries(
  DOC_TYPES.map((d) => [d.value, d.labelKey]),
) as Record<string, keyof Dictionary["docs"]["types"]>;

/** Whether the document detail (extracted items) is worth fetching yet. */
function hasDetail(status: DocumentStatus): boolean {
  return status === "extracted" || status === "verified" || status === "failed";
}

export function DocumentVerifyCard({
  document,
  patientId,
}: {
  document: DocumentSummary;
  patientId: string;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(document.status === "extracted");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const detailEnabled = open && hasDetail(document.status);
  const { data: detail, isLoading } = useDocument(document.id, detailEnabled);
  const verify = useVerifyDocument(patientId);

  const items = useMemo(() => detail?.items ?? [], [detail]);
  const unverified = useMemo(
    () => items.filter((i) => !i.verified),
    [items],
  );

  const typeLabelKey = DOC_TYPE_LABEL_KEYS[document.doc_type];
  const typeLabel = typeLabelKey
    ? t.docs.types[typeLabelKey]
    : document.doc_type;

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function verifyAll() {
    verify.mutate({ documentId: document.id });
    setSelected(new Set());
  }

  function verifySelected() {
    const ids = Array.from(selected);
    if (ids.length === 0) return;
    verify.mutate({ documentId: document.id, itemIds: ids });
    setSelected(new Set());
  }

  const selectableIds = unverified.map((i) => i.id);
  const allSelected =
    selectableIds.length > 0 && selectableIds.every((id) => selected.has(id));

  return (
    <li className="overflow-hidden rounded-lg border border-border bg-surface shadow-card">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-surface-muted/50"
        aria-expanded={open}
      >
        <div className="flex min-w-0 items-center gap-3">
          <span className="text-muted" aria-hidden>
            <FileText className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-foreground">
              {document.filename}
            </p>
            <p className="text-xs text-muted">{typeLabel}</p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <StatusBadge status={document.status} />
          <ChevronDown
            className={cn(
              "h-4 w-4 text-muted transition-transform",
              open && "rotate-180",
            )}
            aria-hidden
          />
        </div>
      </button>

      {open && (
        <div className="border-t border-border px-4 py-3">
          {document.status === "uploaded" || document.status === "processing" ? (
            <p className="flex items-center gap-2 text-sm text-muted">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              {t.docs.processingItems}
            </p>
          ) : document.status === "failed" ? (
            <p className="flex items-center gap-2 text-sm text-danger">
              <AlertTriangle className="h-4 w-4" aria-hidden />
              {detail?.error ?? t.docs.failedTitle}
            </p>
          ) : isLoading ? (
            <p className="flex items-center gap-2 text-sm text-muted">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              {t.common.loading}
            </p>
          ) : items.length === 0 ? (
            <p className="text-sm text-muted">{t.docs.noItemsYet}</p>
          ) : (
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-medium uppercase tracking-wide text-muted">
                  {t.docs.extractedItems} ({items.length})
                </span>
                {selectableIds.length > 0 && (
                  <button
                    type="button"
                    onClick={() =>
                      setSelected(
                        allSelected ? new Set() : new Set(selectableIds),
                      )
                    }
                    className="text-xs font-medium text-primary hover:underline"
                  >
                    {t.docs.selectAll}
                  </button>
                )}
              </div>

              <ul className="flex flex-col gap-2">
                {items.map((item) => (
                  <ClinicalItemRow
                    key={item.id}
                    item={item}
                    checked={selected.has(item.id)}
                    onToggle={() => toggle(item.id)}
                    verifiedLabel={t.docs.verified}
                    needsLabel={t.docs.needsVerification}
                    confidenceLabel={t.docs.confidence}
                    kindLabel={CLINICAL_KIND_LABEL[item.kind]}
                  />
                ))}
              </ul>

              {unverified.length > 0 && (
                <div className="flex flex-wrap items-center gap-2 pt-1">
                  <Button
                    size="sm"
                    onClick={verifyAll}
                    disabled={verify.isPending}
                  >
                    {verify.isPending && (
                      <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                    )}
                    {t.docs.verifyAll}
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={verifySelected}
                    disabled={verify.isPending || selected.size === 0}
                  >
                    {t.docs.verifySelected}
                    {selected.size > 0 ? ` (${selected.size})` : ""}
                  </Button>
                  {verify.isError && (
                    <span className="text-xs text-danger">{t.common.error}</span>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </li>
  );
}

function ClinicalItemRow({
  item,
  checked,
  onToggle,
  verifiedLabel,
  needsLabel,
  confidenceLabel,
  kindLabel,
}: {
  item: ClinicalItem;
  checked: boolean;
  onToggle: () => void;
  verifiedLabel: string;
  needsLabel: string;
  confidenceLabel: string;
  kindLabel: string;
}) {
  const lowConfidence = item.confidence < LOW_CONFIDENCE;
  const pct = Math.round(item.confidence * 100);
  const valueText = [item.value, item.unit].filter(Boolean).join(" ");

  return (
    <li
      className={cn(
        "flex items-start gap-3 rounded-md border px-3 py-2.5",
        item.verified
          ? "border-success/30 bg-success-surface/30"
          : lowConfidence
            ? "border-warning/40 bg-warning-surface/30"
            : "border-border bg-surface",
      )}
    >
      {!item.verified && (
        <input
          type="checkbox"
          checked={checked}
          onChange={onToggle}
          aria-label={`Select ${item.label}`}
          className="mt-1 h-4 w-4 shrink-0 rounded border-border accent-primary"
        />
      )}
      {item.verified && (
        <CheckCircle2
          className="mt-0.5 h-4 w-4 shrink-0 text-success"
          aria-hidden
        />
      )}
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="neutral">{kindLabel}</Badge>
          <span className="text-sm font-medium text-foreground">
            {item.label}
          </span>
          {valueText && (
            <span className="text-sm text-muted">{valueText}</span>
          )}
          {item.date && (
            <span className="text-xs text-muted">· {item.date}</span>
          )}
        </div>
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1">
        {item.verified ? (
          <Badge tone="success">{verifiedLabel}</Badge>
        ) : lowConfidence ? (
          <Badge tone="warning">{needsLabel}</Badge>
        ) : null}
        <span
          className={cn(
            "text-[11px]",
            lowConfidence ? "text-warning" : "text-muted",
          )}
          title={confidenceLabel}
        >
          {confidenceLabel}: {pct}%
        </span>
      </div>
    </li>
  );
}
