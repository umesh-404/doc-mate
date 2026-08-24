import { cn } from "@/lib/utils";

export interface SectionProps {
  title: string;
  icon?: React.ReactNode;
  count?: number;
  /** Highlight the section frame (used for Allergies). */
  tone?: "default" | "danger";
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}

/**
 * A titled block used to structure the Patient Snapshot. Keeps a consistent
 * header rhythm and generous whitespace so the doctor can scan top-to-bottom.
 */
export function Section({
  title,
  icon,
  count,
  tone = "default",
  action,
  children,
  className,
}: SectionProps) {
  return (
    <section
      className={cn(
        "rounded-lg border bg-surface shadow-card",
        tone === "danger"
          ? "border-danger/30 bg-danger-surface/40"
          : "border-border",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-3 border-b border-inherit px-5 py-3">
        <div className="flex items-center gap-2">
          {icon && (
            <span
              className={cn(
                tone === "danger" ? "text-danger" : "text-muted",
              )}
              aria-hidden
            >
              {icon}
            </span>
          )}
          <h2
            className={cn(
              "text-sm font-semibold uppercase tracking-wide",
              tone === "danger" ? "text-danger" : "text-muted",
            )}
          >
            {title}
          </h2>
          {typeof count === "number" && (
            <span className="text-xs text-muted">({count})</span>
          )}
        </div>
        {action}
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}
