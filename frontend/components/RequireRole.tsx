"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { AppHeader } from "@/components/AppHeader";
import { useAuth } from "@/lib/auth";
import type { Role } from "@/lib/api";

/**
 * Client-side route guard for the demo. Redirects unauthenticated users to the
 * login screen and users with the wrong role to their own home. Wraps content
 * with the shared app header once access is granted.
 */
export function RequireRole({
  role,
  children,
}: {
  role: Role;
  children: React.ReactNode;
}) {
  const router = useRouter();
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
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted">
        Loading…
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg">
      <AppHeader />
      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </div>
  );
}
