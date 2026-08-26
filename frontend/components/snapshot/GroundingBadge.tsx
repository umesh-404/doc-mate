"use client";

import { ShieldCheck } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import type { Grounding } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Compact "Grounded NN%" badge with a hover tooltip describing the method and
 * how many lines lacked source support. Framed as reassurance, not alarm: high
 * scores are calm success-green, lower scores are neutral (never red).
 */
export function GroundingBadge({ grounding }: { grounding: Grounding }) {
  const { t } = useI18n();
  const pct = Math.round((grounding.score ?? 0) * 100);
  const strong = pct >= 85;

  const tip = `${t.snapshot.groundingMethod}: ${grounding.method} · ${t.snapshot.groundingUnsupported}: ${grounding.unsupported_count}`;

  return (
    <span
      title={tip}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
        strong
          ? "border-success/20 bg-success-surface text-success"
          : "border-border bg-surface-muted text-muted",
      )}
    >
      <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
      {t.snapshot.grounded} {pct}%
    </span>
  );
}
