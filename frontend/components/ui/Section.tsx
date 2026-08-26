import { cn } from "@/lib/utils";

export interface SectionProps {
  title: string;
  icon?: React.ReactNode;
  count?: number;
  /** Highlight the section frame (used for Allergies, flags, med-safety). */
  tone?: "default" | "danger" | "warning";
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  /** Anchor id — used by the j/k section navigation on the snapshot. */
  id?: string;
  /** Marks the section as the current keyboard-navigation target. */
  active?: boolean;
}

const toneFrame = {
  default: "border-border",
  /* Allergies: a red frame plus a red accent rail so it reads as danger even
     at a glance, in both themes. Never softened. */
  danger:
    "border-danger/40 shadow-[inset_3px_0_0_0_hsl(var(--danger))] bg-danger-surface/40",
  warning:
    "border-warning/40 shadow-[inset_3px_0_0_0_hsl(var(--warning))] bg-warning-surface/30",
} as const;

const toneHeader = {
  default: "text-muted",
  danger: "text-danger",
  warning: "text-warning",
} as const;

/**
 * A titled block used to structure the Patient Snapshot. Keeps a consistent
 * header rhythm so the doctor can scan top-to-bottom: small uppercase eyebrow,
 * hairline rule, then dense content.
 */
export function Section({
  title,
  icon,
  count,
  tone = "default",
  action,
  children,
  className,
  id,
  active,
}: SectionProps) {
  return (
    <section
      id={id}
      tabIndex={id ? -1 : undefined}
      aria-labelledby={id ? `${id}-heading` : undefined}
      data-section={id}
      className={cn(
        "avoid-break min-w-0 scroll-mt-36 rounded-lg border bg-surface shadow-card",
        "transition-[box-shadow,border-color] duration-200 ease-clinical",
        "focus:outline-none",
        toneFrame[tone],
        active && "ring-2 ring-ring/40 ring-offset-2 ring-offset-bg",
        className,
      )}
    >
      <div
        className={cn(
          "flex items-center justify-between gap-3 border-b px-4 py-2.5 sm:px-5",
          tone === "default" ? "border-border" : "border-inherit",
        )}
      >
        <div className="flex min-w-0 items-center gap-2">
          {icon && (
            <span className={cn("shrink-0", toneHeader[tone])} aria-hidden>
              {icon}
            </span>
          )}
          <h2
            id={id ? `${id}-heading` : undefined}
            className={cn(
              "truncate text-2xs font-bold uppercase tracking-[0.09em]",
              toneHeader[tone],
            )}
          >
            {title}
          </h2>
          {typeof count === "number" && count > 0 && (
            <span
              className={cn(
                "shrink-0 rounded-full px-1.5 py-px text-2xs font-semibold tabular-nums",
                tone === "default"
                  ? "bg-surface-muted text-muted"
                  : "bg-surface/70 text-current",
              )}
            >
              {count}
            </span>
          )}
        </div>
        {action}
      </div>
      <div className="p-4 sm:p-5">{children}</div>
    </section>
  );
}
