"use client";

/**
 * Connectivity + sync status for the app header.
 *
 * PROJECT.md §4 rule 5 (faithful status reporting) is the whole point of this
 * component: the user always knows whether they are online, how much work has
 * not reached the server, and which items went wrong. Nothing here ever reports
 * success for a write the server has not accepted.
 */

import {
  AlertTriangle,
  CloudOff,
  Loader2,
  RefreshCw,
  Trash2,
  UploadCloud,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useI18n } from "@/lib/i18n";
import type { Dictionary } from "@/lib/i18n/dictionaries";
import type { OutboxRecord } from "@/lib/offline/db";
import { fill } from "@/lib/offline/format";
import { MAX_ATTEMPTS } from "@/lib/offline/outbox";
import { useOffline } from "@/lib/offline/provider";
import { cn } from "@/lib/utils";

function kindLabel(kind: OutboxRecord["kind"], t: Dictionary): string {
  switch (kind) {
    case "create_patient":
      return t.offline.itemPatient;
    case "upload_document":
      return t.offline.itemDocument;
    case "verify_document":
      return t.offline.itemVerify;
    default:
      return t.offline.itemRaw;
  }
}

export function SyncIndicator() {
  const { t } = useI18n();
  const {
    online,
    outbox,
    pendingCount,
    attentionCount,
    syncing,
    syncNow,
    retryItem,
    discardItem,
  } = useOffline();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  // Close the panel on an outside click or Escape, like the other popovers.
  useEffect(() => {
    if (!open) return;
    const onPointer = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const queued = pendingCount + attentionCount;

  // Fully synced and connected is the normal state — say nothing.
  if (online && queued === 0) return null;

  const tone = attentionCount > 0 ? "danger" : online ? "primary" : "warning";

  return (
    <div ref={wrapRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={t.offline.openQueue}
        className={cn(
          "inline-flex h-8 items-center gap-1.5 rounded-full border px-2.5",
          "text-2xs font-semibold transition-colors duration-150 ease-clinical",
          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
          tone === "danger" && "border-danger/40 bg-danger-surface text-danger",
          tone === "warning" && "border-warning/45 bg-warning-surface text-warning",
          tone === "primary" && "border-primary/30 bg-primary/10 text-primary",
        )}
      >
        {!online ? (
          <CloudOff className="h-3.5 w-3.5" aria-hidden />
        ) : syncing ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
        ) : attentionCount > 0 ? (
          <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
        ) : (
          <UploadCloud className="h-3.5 w-3.5" aria-hidden />
        )}
        <span>{!online ? t.offline.offline : t.offline.queueTitle}</span>
        {queued > 0 && (
          <span className="rounded-full bg-surface/70 px-1.5 tabular-nums">
            {queued}
          </span>
        )}
      </button>

      {/* Screen-reader announcement of the connectivity change. */}
      <span className="sr-only" role="status" aria-live="polite">
        {online ? t.offline.online : t.offline.offline}
      </span>

      {open && (
        <div
          className="absolute right-0 z-40 mt-2 w-[min(22rem,calc(100vw-2rem))] animate-rise-in rounded-lg border border-border bg-surface-raised p-3 shadow-float"
          role="dialog"
          aria-label={t.offline.queueTitle}
        >
          {!online && (
            <p className="mb-3 rounded-md border border-warning/45 bg-warning-surface px-3 py-2 text-xs font-medium leading-relaxed text-warning">
              {t.offline.offlineBanner}
            </p>
          )}

          <div className="mb-2 flex items-center justify-between gap-2">
            <h2 className="text-2xs font-bold uppercase tracking-[0.09em] text-muted">
              {t.offline.queueTitle}
            </h2>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => void syncNow()}
              disabled={!online || syncing || pendingCount === 0}
            >
              {syncing ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
              ) : (
                <RefreshCw className="h-3.5 w-3.5" aria-hidden />
              )}
              {syncing ? t.offline.syncing : t.offline.syncNow}
            </Button>
          </div>

          {outbox.length === 0 ? (
            <p className="py-3 text-center text-xs text-muted">
              {t.offline.queueEmpty}
            </p>
          ) : (
            <ul className="flex max-h-80 flex-col gap-2 overflow-y-auto">
              {outbox.map((item) => (
                <QueueRow
                  key={item.id}
                  item={item}
                  onRetry={() => void retryItem(item.id)}
                  onDiscard={() => {
                    if (window.confirm(t.offline.discardConfirm)) {
                      void discardItem(item.id);
                    }
                  }}
                />
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function QueueRow({
  item,
  onRetry,
  onDiscard,
}: {
  item: OutboxRecord;
  onRetry: () => void;
  onDiscard: () => void;
}) {
  const { t } = useI18n();
  const needsAttention = item.state === "failed" || item.state === "conflict";

  // The reason a write did not land is stated in the user's own terms — an
  // interrupted send is called out separately because it is genuinely
  // ambiguous and must not be blind-retried.
  const reason =
    item.lastError === "interrupted"
      ? t.offline.interrupted
      : item.state === "conflict"
        ? `${t.offline.rejected}${item.lastStatus ? ` (${item.lastStatus})` : ""}`
        : item.state === "failed"
          ? fill(t.offline.failedAfterRetries, MAX_ATTEMPTS)
          : item.state === "inflight"
            ? t.offline.syncing
            : t.offline.queued;

  return (
    <li
      className={cn(
        "rounded-md border px-3 py-2",
        needsAttention
          ? "border-danger/35 bg-danger-surface/60"
          : "border-border bg-surface",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-xs font-semibold text-foreground">
            {item.label || kindLabel(item.kind, t)}
          </p>
          <p className="truncate text-2xs text-muted">
            {kindLabel(item.kind, t)}
          </p>
        </div>
        <Badge tone={needsAttention ? "danger" : "warning"}>
          {needsAttention ? t.offline.attentionTitle : t.offline.queuedShort}
        </Badge>
      </div>

      <p
        className={cn(
          "mt-1 text-2xs leading-relaxed",
          needsAttention ? "font-medium text-danger" : "text-muted",
        )}
      >
        {reason}
        {item.attempts > 0 && !needsAttention && (
          <span className="ml-1 tabular-nums">
            · {fill(t.offline.attemptsLabel, item.attempts)}
          </span>
        )}
      </p>

      {needsAttention && (
        <div className="mt-2 flex items-center gap-2">
          <Button size="sm" variant="secondary" onClick={onRetry}>
            <RefreshCw className="h-3 w-3" aria-hidden />
            {t.offline.retry}
          </Button>
          <Button size="sm" variant="ghost" onClick={onDiscard}>
            <Trash2 className="h-3 w-3" aria-hidden />
            {t.offline.discard}
          </Button>
        </div>
      )}
    </li>
  );
}
