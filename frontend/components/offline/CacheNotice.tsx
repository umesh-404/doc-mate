"use client";

/**
 * "Offline copy · synced 12 min ago" — the label that keeps cached clinical
 * data from masquerading as live (PROJECT.md §4 rule 5).
 *
 * Shown whenever the screen is being read from the local cache: while the
 * device is offline, and while a request is failing but stale data is still on
 * screen. It re-renders on a timer so the age never freezes at "just now".
 */

import { CloudOff } from "lucide-react";
import { useEffect, useState } from "react";
import type { QueryKey } from "@tanstack/react-query";
import { useI18n } from "@/lib/i18n";
import { formatAgo } from "@/lib/offline/format";
import { useOffline } from "@/lib/offline/provider";
import { cn } from "@/lib/utils";

export function CacheNotice({
  queryKey,
  /** Pass true when the query has data but its last refresh failed. */
  stale = false,
  className,
}: {
  queryKey: QueryKey;
  stale?: boolean;
  className?: string;
}) {
  const { t } = useI18n();
  const { online, lastSyncedAt } = useOffline();
  const fetchedAt = lastSyncedAt(queryKey);
  const [, tick] = useState(0);

  // Keep the relative age honest without a re-render storm.
  useEffect(() => {
    const timer = window.setInterval(() => tick((n) => n + 1), 30_000);
    return () => window.clearInterval(timer);
  }, []);

  if (online && !stale) return null;

  return (
    <p
      role="note"
      className={cn(
        "flex items-center gap-1.5 rounded-md border border-warning/45 bg-warning-surface",
        "px-3 py-1.5 text-2xs font-semibold text-warning print:hidden",
        className,
      )}
    >
      <CloudOff className="h-3.5 w-3.5 shrink-0" aria-hidden />
      <span>
        {t.offline.cachedCopy} · {t.offline.syncedPrefix}{" "}
        {formatAgo(fetchedAt, t)}
      </span>
    </p>
  );
}
