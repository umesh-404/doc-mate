import { cn } from "@/lib/utils";

type Tone = "neutral" | "primary" | "danger" | "warning" | "success";

const tones: Record<Tone, string> = {
  neutral: "bg-surface-muted text-muted border-border",
  primary: "bg-primary/10 text-primary border-primary/20",
  danger: "bg-danger-surface text-danger border-danger/20",
  warning: "bg-warning-surface text-warning border-warning/20",
  success: "bg-success-surface text-success border-success/20",
};

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
}

export function Badge({ className, tone = "neutral", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}
