"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { AppHeader } from "@/components/AppHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import type { Role } from "@/lib/api";

/**
 * Client-side route guard for the demo. Redirects unauthenticated users to the
 * login screen and users with the wrong role to their own home. Wraps content
 * with the shared app header once access is granted.
 */
export function RequireRole({
  role,
  children,
  headerActions,
}: {
  role: Role;
  children: React.ReactNode;
  /** Extra controls slotted into the app header (e.g. shortcuts hint). */
  headerActions?: React.ReactNode;
}) {
  const router = useRouter();
  const { t } = useI18n();
  const { status, role: userRole } = useAuth();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace("/");
    } else if (status === "authenticated" && userRole && userRole !== role) {
      router.replace(
        userRole === "doctor" ? "/doctor/patients" : "/reception/patients",
      );
    }
  }, [status, userRole, role, router]);

  if (status !== "authenticated" || userRole !== role) {
    // Shell skeleton rather than a bare "Loading…" — the chrome appears
    // instantly so the transition into the app feels continuous.
    return (
      <div className="min-h-screen bg-bg">
        <div className="border-b border-border bg-surface">
          <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
            <div className="flex items-center gap-2">
              <Skeleton className="h-8 w-8 rounded-md" />
              <Skeleton className="h-4 w-24" />
            </div>
            <Skeleton className="h-8 w-28 rounded-md" />
          </div>
        </div>
        <main
          className="mx-auto max-w-6xl px-4 py-6"
          role="status"
          aria-live="polite"
          aria-busy="true"
        >
          <span className="sr-only">{t.states.loading}</span>
          <Skeleton className="h-8 w-52" />
          <Skeleton className="mt-3 h-3.5 w-72 max-w-full" />
          <Skeleton className="mt-6 h-64 w-full rounded-lg" />
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg">
      <AppHeader actions={headerActions} />
      <main id="main" className="mx-auto max-w-6xl px-4 py-5 sm:py-6">
        {children}
      </main>
    </div>
  );
}
