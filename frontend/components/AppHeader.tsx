"use client";

import { Activity, LogOut } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

/** Top navigation bar shared across authenticated screens. */
export function AppHeader() {
  const { user, role, logout } = useAuth();
  const { t } = useI18n();
  const home = role === "doctor" ? "/doctor/patients" : "/reception/patients";

  return (
    <header className="sticky top-0 z-20 border-b border-border bg-surface/90 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-4">
        <Link href={home} className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <Activity className="h-5 w-5" aria-hidden />
          </span>
          <span className="text-lg font-semibold tracking-tight text-foreground">
            {t.appName}
          </span>
          {role && (
            <Badge tone="primary" className="ml-1">
              {role === "doctor" ? t.roles.doctor : t.roles.reception}
            </Badge>
          )}
        </Link>

        <div className="flex items-center gap-3">
          <LanguageSwitcher />
          {user && (
            <span className="hidden text-sm text-muted sm:inline">
              {user.name}
            </span>
          )}
          <Button variant="ghost" size="sm" onClick={logout}>
            <LogOut className="h-4 w-4" aria-hidden />
            <span className="hidden sm:inline">{t.common.signOut}</span>
          </Button>
        </div>
      </div>
    </header>
  );
}
