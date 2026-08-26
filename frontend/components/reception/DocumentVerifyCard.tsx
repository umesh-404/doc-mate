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
  const unverified = useMemo(() => items.filter((i) => !i.verified), [items]);
  const lowConfidenceCount = useMemo(
    () => unverified.filter((i) => i.confidence < LOW_CONFIDENCE).length,
    [unverified],
  );

  const typeLabelKey = DOC_TYPE_LABEL_KEYS[document.doc_type];
  const typeLabel = typeLabelKey
    ? t.docs.types[typeLabelKey]
    : document.doc_type;

  const panelId = `doc-panel-${document.id}`;

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
    <li
      className={cn(
        "overflow-hidden rounded-lg border bg-surface shadow-card",
        "transition-[border-color,box-shadow] duration-200 ease-clinical",
        document.status === "failed"
          ? "border-danger/40"
          : lowConfidenceCount > 0
            ? "border-warning/45"
            : "border-border",
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-3.5 py-3 text-left transition-colors hover:bg-surface-muted/60 sm:px-4"
        aria-expanded={open}
        aria-controls={panelId}
      >
        <div className="flex min-w-0 items-center gap-3">
          <span
            className={cn(
              "flex h-9 w-9 shrink-0 items-center justify-center rounded-md border",
              document.status === "failed"
                ? "border-danger/30 bg-danger-surface text-danger"
                : "border-border bg-surface-muted text-muted",
            )}
            aria-hidden
          >
            <FileText className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-foreground">
              {document.filename}
            </p>
            <p className="text-xs text-muted">{typeLabel}</p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {lowConfidenceCount > 0 && (
            <Badge tone="warning" data-verify-marker className="hidden sm:inline-flex">
              {lowConfidenceCount} {t.docs.needsVerification}
            </Badge>
          )}
          <StatusBadge status={document.status} />
          <ChevronDown
            className={cn(
              "h-4 w-4 shrink-0 text-muted transition-transform duration-200 ease-clinical",
              open && "rotate-180",
            )}
            aria-hidden
          />
        </div>
      </button>

      {open && (
        <div
          id={panelId}
          className="animate-expand-down border-t border-border px-3.5 py-3 sm:px-4"
        >
          {document.status === "uploaded" || document.status === "processing" ? (
            <p
              className="flex items-center gap-2 text-sm text-muted"
              role="status"
              aria-live="polite"
            >
              <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" aria-hidden />
              {t.docs.processingItems}
            </p>
          ) : document.status === "failed" ? (
            /* Faithful status reporting (PROJECT.md §4.5): a failure is stated
               plainly, never hidden behind an empty list. */
            <p
              role="alert"
              className="flex items-start gap-2 rounded-md border border-danger/35 bg-danger-surface px-3 py-2.5 text-sm font-medium text-danger"
            >
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              {detail?.error ?? t.docs.failedTitle}
            </p>
          ) : isLoading ? (
            <p
              className="flex items-center gap-2 text-sm text-muted"
              role="status"
              aria-live="polite"
            >
              <Loader2 className="h-4 w-4 animate-spin text-primary" aria-hidden />
              {t.common.loading}
            </p>
          ) : items.length === 0 ? (
            <p className="text-sm text-muted">{t.docs.noItemsYet}</p>
          ) : (
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-2xs font-bold uppercase tracking-[0.08em] text-muted">
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
                    className="rounded text-xs font-semibold text-primary underline-offset-4 hover:underline"
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

              <p className="sr-only" aria-live="polite">
                {unverified.length === 0
                  ? t.docs.verified
                  : `${unverified.length} ${t.docs.needsVerification}`}
              </p>

              {unverified.length > 0 ? (
                <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
                  <Button size="sm" onClick={verifyAll} disabled={verify.isPending}>
                    {verify.isPending ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                    ) : (
                      <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
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
                    <span role="alert" className="text-xs font-medium text-danger">
                      {t.common.error}
                    </span>
                  )}
                </div>
              ) : (
                <p className="flex items-center gap-2 border-t border-border pt-3 text-xs font-medium text-success">
                  <CheckCircle2 className="h-4 w-4 shrink-0" aria-hidden />
                  {t.docs.verified}
                </p>
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

  // The whole row is the label for its checkbox — a big, forgiving hit target
  // for a busy front desk, including on touch.
  const Wrapper = item.verified ? "div" : "label";

  return (
    <li>
      <Wrapper
        className={cn(
          "flex items-start gap-3 rounded-md border px-3 py-2.5",
          "transition-colors duration-150 ease-clinical",
          item.verified
            ? "border-success/35 bg-success-surface/50"
            : lowConfidence
              ? "cursor-pointer border-warning/50 bg-warning-surface/50 hover:border-warning"
              : "cursor-pointer border-border bg-surface hover:border-border-strong hover:bg-surface-muted/50",
        )}
      >
        {item.verified ? (
          <CheckCircle2
            className="mt-0.5 h-4 w-4 shrink-0 text-success"
            aria-hidden
          />
        ) : (
          <input
            type="checkbox"
            checked={checked}
            onChange={onToggle}
            className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer rounded border-control-border accent-primary"
          />
        )}

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <Badge tone="outline">{kindLabel}</Badge>
            <span className="text-sm font-semibold text-foreground">
              {item.label}
            </span>
            {valueText && (
              <span className="text-sm font-medium tabular-nums text-foreground-subtle">
                {valueText}
              </span>
            )}
            {item.date && (
              <span className="text-xs tabular-nums text-muted">
                · {item.date}
              </span>
            )}
          </div>

          {/* Confidence meter — a proportion is easier to judge at a glance
              than a bare percentage, and low values stay conspicuously amber. */}
          <div className="mt-1.5 flex items-center gap-2">
            <span
              className="h-1 w-16 shrink-0 overflow-hidden rounded-full bg-border"
              role="img"
              aria-label={`${confidenceLabel}: ${pct}%`}
            >
              <span
                className={cn(
                  "block h-full rounded-full",
                  lowConfidence ? "bg-warning" : "bg-success",
                )}
                style={{ width: `${Math.max(4, Math.min(100, pct))}%` }}
              />
            </span>
            <span
              className={cn(
                "text-2xs font-medium tabular-nums",
                lowConfidence ? "text-warning" : "text-muted",
              )}
            >
              {confidenceLabel}: {pct}%
            </span>
          </div>
        </div>

        <div className="flex shrink-0 items-center">
          {item.verified ? (
            <Badge tone="success">{verifiedLabel}</Badge>
          ) : lowConfidence ? (
            <Badge tone="warning" data-verify-marker>
              {needsLabel}
            </Badge>
          ) : null}
        </div>
      </Wrapper>
    </li>
  );
}
