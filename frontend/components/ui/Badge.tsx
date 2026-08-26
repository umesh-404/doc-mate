import { cn } from "@/lib/utils";

type Tone = "neutral" | "primary" | "danger" | "warning" | "success" | "outline";

/**
 * Tones carry meaning, not decoration:
 *  danger  → allergy / high severity / failed
 *  warning → needs verification, low confidence  (must stay conspicuous)
 *  success → verified, grounded
 */
const tones: Record<Tone, string> = {
  neutral: "bg-surface-muted text-foreground-subtle border-border",
  outline: "bg-transparent text-muted border-border",
  primary: "bg-primary/10 text-primary border-primary/25",
  danger: "bg-danger-surface text-danger border-danger/35",
  warning: "bg-warning-surface text-warning border-warning/40",
  success: "bg-success-surface text-success border-success/30",
};

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
}

export function Badge({ className, tone = "neutral", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-full border",
        "px-2 py-0.5 text-2xs font-semibold leading-normal",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}
