import { forwardRef } from "react";
import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "subtle";
type Size = "sm" | "md" | "lg" | "icon";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const variants: Record<Variant, string> = {
  primary:
    "bg-primary text-primary-foreground shadow-card hover:bg-primary-hover active:shadow-none",
  secondary:
    "bg-surface text-foreground border border-control-border shadow-card hover:border-accent/70 hover:bg-surface-muted active:shadow-none",
  subtle:
    "bg-surface-muted text-foreground-subtle hover:bg-border/60 hover:text-foreground",
  ghost:
    "bg-transparent text-foreground-subtle hover:bg-surface-muted hover:text-foreground",
  danger:
    "bg-danger text-danger-foreground shadow-card hover:bg-danger-strong active:shadow-none",
};

const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-xs gap-1.5",
  md: "h-10 px-4 text-sm gap-2",
  lg: "h-11 px-6 text-base gap-2",
  // Square target that still clears the 44px touch guidance on coarse pointers.
  icon: "h-9 w-9 p-0",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", type, ...props }, ref) => {
    return (
      <button
        ref={ref}
        type={type ?? "button"}
        className={cn(
          "inline-flex select-none items-center justify-center rounded-md font-medium",
          "transition-[background-color,border-color,color,box-shadow,transform] duration-150 ease-clinical",
          // Tactile press feedback — a hair of travel, nothing bouncy.
          "active:translate-y-px",
          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
          "disabled:pointer-events-none disabled:opacity-50",
          variants[variant],
          sizes[size],
          className,
        )}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";
