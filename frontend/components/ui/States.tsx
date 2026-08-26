"use client";

import { AlertTriangle, Inbox, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";

/**
 * Inline loading indicator. Prefer a Skeleton* component wherever the final
 * layout is known — this is the fallback for small, in-place waits.
 */
export function LoadingState({
  label,
  className,
}: {
  label: string;
  className?: string;
}) {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-busy="true"
      className={cn(
        "flex animate-fade-in items-center justify-center gap-2.5 rounded-lg border border-border",
        "bg-surface px-4 py-12 text-sm text-muted shadow-card",
        className,
      )}
    >
      <Loader2 className="h-4 w-4 animate-spin text-primary" aria-hidden />
      {label}
    </div>
  );
}

/**
 * Error panel. Deliberately plain-spoken and reassuring — per PROJECT.md §4.5
 * a failure is stated, never hidden behind a confident-looking empty screen.
 */
export function ErrorState({
  title,
  body,
  onRetry,
  retryLabel,
  className,
}: {
  title: string;
  body?: string;
  onRetry?: () => void;
  retryLabel?: string;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn(
        "flex animate-rise-in flex-col items-center gap-3 rounded-lg border border-danger/35",
        "bg-danger-surface/50 px-6 py-10 text-center shadow-card",
        className,
      )}
    >
      <span className="flex h-11 w-11 items-center justify-center rounded-full border border-danger/30 bg-danger-surface text-danger">
        <AlertTriangle className="h-5 w-5" aria-hidden />
      </span>
      <div className="max-w-sm">
        <p className="text-md font-semibold text-foreground">{title}</p>
        {body && (
          <p className="mt-1 text-sm leading-relaxed text-muted">{body}</p>
        )}
      </div>
      {onRetry && retryLabel && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          <RefreshCw className="h-3.5 w-3.5" aria-hidden />
          {retryLabel}
        </Button>
      )}
    </div>
  );
}

/** Empty-state placeholder — calm, never alarming. */
export function EmptyState({
  title,
  body,
  icon,
  action,
  className,
}: {
  title: string;
  body?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex animate-rise-in flex-col items-center gap-3 rounded-lg border border-dashed border-border-strong/70",
        "bg-surface-muted/40 px-6 py-12 text-center",
        className,
      )}
    >
      <span className="flex h-11 w-11 items-center justify-center rounded-full border border-border bg-surface text-muted shadow-card">
        {icon ?? <Inbox className="h-5 w-5" aria-hidden />}
      </span>
      <div className="max-w-sm">
        <p className="text-md font-semibold text-foreground">{title}</p>
        {body && (
          <p className="mt-1 text-sm leading-relaxed text-muted">{body}</p>
        )}
      </div>
      {action}
    </div>
  );
}
