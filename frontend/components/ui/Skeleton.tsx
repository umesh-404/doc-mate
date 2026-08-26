import { cn } from "@/lib/utils";

/**
 * Skeleton primitives. Each loader below mirrors the geometry of the screen it
 * replaces, so the layout does not jump when real data lands.
 */
export function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("skeleton", className)} {...props} />;
}

/** A titled card block: eyebrow rule + N content rows. */
export function SkeletonSection({
  rows = 3,
  className,
}: {
  rows?: number;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "overflow-hidden rounded-lg border border-border bg-surface shadow-card",
        className,
      )}
    >
      <div className="flex items-center gap-2 border-b border-border px-5 py-3">
        <Skeleton className="h-3.5 w-3.5 rounded-full" />
        <Skeleton className="h-3 w-32" />
      </div>
      <div className="flex flex-col gap-2.5 p-5">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex items-center justify-between gap-4">
            <Skeleton
              className="h-4 flex-1"
              style={{ maxWidth: `${88 - i * 11}%` }}
            />
            <Skeleton className="h-4 w-20 shrink-0 rounded-full" />
          </div>
        ))}
      </div>
    </div>
  );
}

/** Full Patient Snapshot skeleton — identity bar, alerts, then sections. */
export function SnapshotSkeleton({ label }: { label: string }) {
  return (
    <div
      className="flex animate-fade-in flex-col gap-4"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <span className="sr-only">{label}</span>

      {/* Identity bar */}
      <div className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-5 shadow-card sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-2">
          <Skeleton className="h-7 w-56" />
          <Skeleton className="h-3.5 w-72 max-w-full" />
        </div>
        <Skeleton className="h-7 w-32 rounded-full" />
      </div>

      {/* Alerts */}
      <div className="flex flex-col gap-2">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-14 w-full rounded-lg" />
        <Skeleton className="h-14 w-full rounded-lg" />
      </div>

      <SkeletonSection rows={2} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <SkeletonSection rows={3} />
        <SkeletonSection rows={3} />
      </div>
      <SkeletonSection rows={4} />
    </div>
  );
}

/** Patient table skeleton. */
export function SkeletonTable({
  rows = 6,
  label,
}: {
  rows?: number;
  label: string;
}) {
  return (
    <div
      className="flex animate-fade-in flex-col gap-4"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <span className="sr-only">{label}</span>
      <Skeleton className="h-10 w-full max-w-md" />
      <div className="overflow-hidden rounded-lg border border-border bg-surface shadow-card">
        <div className="border-b border-border bg-surface-muted/60 px-4 py-3">
          <Skeleton className="h-3 w-28" />
        </div>
        {Array.from({ length: rows }).map((_, i) => (
          <div
            key={i}
            className="flex items-center justify-between gap-4 border-b border-border px-4 py-3.5 last:border-b-0"
          >
            <div className="flex flex-1 flex-col gap-1.5">
              <Skeleton className="h-3.5 w-40 max-w-[60%]" />
              <Skeleton className="h-2.5 w-24" />
            </div>
            <Skeleton className="hidden h-3 w-28 sm:block" />
            <Skeleton className="h-3 w-4" />
          </div>
        ))}
      </div>
    </div>
  );
}

/** Document list skeleton for the reception verify column. */
export function SkeletonDocList({
  rows = 3,
  label,
}: {
  rows?: number;
  label: string;
}) {
  return (
    <div
      className="flex animate-fade-in flex-col gap-3"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface px-4 py-3.5 shadow-card"
        >
          <div className="flex min-w-0 flex-1 items-center gap-3">
            <Skeleton className="h-8 w-8 shrink-0 rounded-md" />
            <div className="flex min-w-0 flex-1 flex-col gap-1.5">
              <Skeleton className="h-3.5 w-48 max-w-[70%]" />
              <Skeleton className="h-2.5 w-24" />
            </div>
          </div>
          <Skeleton className="h-5 w-20 shrink-0 rounded-full" />
        </div>
      ))}
    </div>
  );
}
