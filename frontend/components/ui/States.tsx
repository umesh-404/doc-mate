"use client";

import { AlertTriangle, Inbox, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/Button";

/** Centered spinner for query loading states. */
export function LoadingState({ label }: { label: string }) {
  return (
    <div
      role="status"
      className="flex items-center justify-center gap-2 rounded-lg border border-border bg-surface px-4 py-12 text-sm text-muted shadow-card"
    >
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
      {label}
    </div>
  );
}

/** Error panel with an optional retry action. */
export function ErrorState({
  title,
  body,
  onRetry,
  retryLabel,
}: {
  title: string;
  body?: string;
  onRetry?: () => void;
  retryLabel?: string;
}) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center gap-3 rounded-lg border border-danger/30 bg-danger-surface/40 px-4 py-10 text-center shadow-card"
    >
      <span className="flex h-10 w-10 items-center justify-center rounded-full bg-danger-surface text-danger">
        <AlertTriangle className="h-5 w-5" aria-hidden />
      </span>
      <div>
        <p className="text-sm font-semibold text-foreground">{title}</p>
        {body && <p className="mt-1 text-sm text-muted">{body}</p>}
      </div>
      {onRetry && retryLabel && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          {retryLabel}
        </Button>
      )}
    </div>
  );
}

/** Empty-state placeholder. */
export function EmptyState({
  title,
  body,
  icon,
  action,
}: {
  title: string;
  body?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-border bg-surface-muted/30 px-4 py-12 text-center">
      <span className="flex h-10 w-10 items-center justify-center rounded-full bg-surface-muted text-muted">
        {icon ?? <Inbox className="h-5 w-5" aria-hidden />}
      </span>
      <div>
        <p className="text-sm font-semibold text-foreground">{title}</p>
        {body && <p className="mt-1 text-sm text-muted">{body}</p>}
      </div>
      {action}
    </div>
  );
}
