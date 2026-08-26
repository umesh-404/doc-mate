import { forwardRef, useId } from "react";
import { cn } from "@/lib/utils";

/** Shared field chrome so inputs, selects and textareas look identical. */
export const fieldClass = cn(
  "w-full rounded-md border border-control-border bg-surface text-sm text-foreground",
  "transition-[border-color,box-shadow] duration-150 ease-clinical",
  "placeholder:text-muted",
  "hover:border-accent/70",
  "focus:border-accent focus:outline-none focus:ring-2 focus:ring-ring/35",
  "disabled:cursor-not-allowed disabled:bg-surface-muted disabled:opacity-60",
);

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  /** Inline validation message. Sets aria-invalid and reddens the field. */
  error?: string | null;
  /** Rendered inside the field on the leading edge (e.g. a search icon). */
  leading?: React.ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, hint, error, leading, id, ...props }, ref) => {
    const reactId = useId();
    const inputId = id ?? props.name ?? reactId;
    const hintId = hint ? `${inputId}-hint` : undefined;
    const errorId = error ? `${inputId}-error` : undefined;

    return (
      <div className="flex w-full flex-col gap-1.5">
        {label && (
          <label
            htmlFor={inputId}
            className="flex items-center gap-1 text-xs font-semibold text-foreground-subtle"
          >
            {label}
            {props.required && (
              <span className="text-danger" aria-hidden>
                *
              </span>
            )}
          </label>
        )}
        <div className="relative">
          {leading && (
            <span
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted"
              aria-hidden
            >
              {leading}
            </span>
          )}
          <input
            ref={ref}
            id={inputId}
            aria-invalid={error ? true : undefined}
            aria-describedby={
              [errorId, hintId].filter(Boolean).join(" ") || undefined
            }
            className={cn(
              fieldClass,
              "h-10 px-3",
              leading && "pl-9",
              error &&
                "border-danger focus:border-danger focus:ring-danger/30",
              className,
            )}
            {...props}
          />
        </div>
        {error ? (
          <p id={errorId} className="text-xs font-medium text-danger">
            {error}
          </p>
        ) : (
          hint && (
            <p id={hintId} className="text-xs text-muted">
              {hint}
            </p>
          )
        )}
      </div>
    );
  },
);
Input.displayName = "Input";

export interface SelectFieldProps
  extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  hint?: string;
}

/** Native select with the shared field chrome and a proper <label>. */
export const SelectField = forwardRef<HTMLSelectElement, SelectFieldProps>(
  ({ className, label, hint, id, children, ...props }, ref) => {
    const reactId = useId();
    const selectId = id ?? props.name ?? reactId;
    const hintId = hint ? `${selectId}-hint` : undefined;

    return (
      <div className="flex w-full flex-col gap-1.5">
        {label && (
          <label
            htmlFor={selectId}
            className="text-xs font-semibold text-foreground-subtle"
          >
            {label}
          </label>
        )}
        <select
          ref={ref}
          id={selectId}
          aria-describedby={hintId}
          className={cn(fieldClass, "h-10 cursor-pointer px-2.5", className)}
          {...props}
        >
          {children}
        </select>
        {hint && (
          <p id={hintId} className="text-xs text-muted">
            {hint}
          </p>
        )}
      </div>
    );
  },
);
SelectField.displayName = "SelectField";

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: React.ReactNode;
  hint?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(fieldClass, "min-h-[5rem] px-3 py-2 leading-relaxed", className)}
      {...props}
    />
  ),
);
Textarea.displayName = "Textarea";
