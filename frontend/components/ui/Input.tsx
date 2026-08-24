import { forwardRef } from "react";
import { cn } from "@/lib/utils";

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, hint, id, ...props }, ref) => {
    const inputId = id ?? props.name;
    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label
            htmlFor={inputId}
            className="text-sm font-medium text-foreground"
          >
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={cn(
            "h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground",
            "placeholder:text-muted",
            "focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30",
            "disabled:cursor-not-allowed disabled:opacity-60",
            className,
          )}
          {...props}
        />
        {hint && <p className="text-xs text-muted">{hint}</p>}
      </div>
    );
  },
);
Input.displayName = "Input";
