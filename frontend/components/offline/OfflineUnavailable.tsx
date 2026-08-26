"use client";

/**
 * Shown when the device is offline and this screen has no cached copy at all.
 *
 * A skeleton that spins forever would imply data is coming; this states plainly
 * that there is nothing saved for this record on this device (PROJECT.md §4
 * rule 5) rather than looking like a slow load.
 */

import { CloudOff } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { EmptyState } from "@/components/ui/States";

export function OfflineUnavailable({ className }: { className?: string }) {
  const { t } = useI18n();
  return (
    <EmptyState
      className={className}
      icon={<CloudOff className="h-5 w-5" aria-hidden />}
      title={t.offline.unavailableTitle}
      body={t.offline.unavailableBody}
    />
  );
}
