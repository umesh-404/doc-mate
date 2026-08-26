"use client";

import { ShieldCheck } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import type { Grounding } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Compact "Grounded NN%" badge with a hover tooltip describing the method and
 * how many lines lacked source support. Framed as reassurance, not alarm: high
 * scores are calm success-green, lower scores are neutral (never red) — a low
 * score means "fewer lines were citable", not "this patient is at risk".
 */
export function GroundingBadge({
  grounding,
  compact,
}: {
  grounding: Grounding;
  compact?: boolean;
}) {
  const { t } = useI18n();
  const pct = Math.round((grounding.score ?? 0) * 100);
  const strong = pct >= 85;

  const tip = `${t.snapshot.groundingMethod}: ${grounding.method} · ${t.snapshot.groundingUnsupported}: ${grounding.unsupported_count}`;

  return (
    <span
      title={tip}
      className={cn(
        "inline-flex shrink-0 items-center gap-1.5 rounded-full border font-semibold",
        compact ? "px-2 py-0.5 text-2xs" : "px-2.5 py-1 text-xs",
        strong
          ? "border-success/35 bg-success-surface text-success"
          : "border-border-strong bg-surface-muted text-foreground-subtle",
      )}
    >
      <ShieldCheck
        className={compact ? "h-3 w-3" : "h-3.5 w-3.5"}
        aria-hidden
      />
      <span className="tabular-nums">
        {t.snapshot.grounded} {pct}%
      </span>
    </span>
  );
}
