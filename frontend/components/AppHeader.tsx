"use client";

import { Activity, LogOut } from "lucide-react";
import Link from "next/link";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

/** Top navigation bar shared across authenticated screens. */
export function AppHeader({ actions }: { actions?: React.ReactNode }) {
  const { user, role, logout } = useAuth();
  const { t } = useI18n();
  const home = role === "doctor" ? "/doctor/patients" : "/reception/patients";

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-surface/85 backdrop-blur-md supports-[backdrop-filter]:bg-surface/70 print:hidden">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-3 px-4">
        <Link
          href={home}
          className="group flex min-w-0 items-center gap-2 rounded-md py-1 pr-2"
        >
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground shadow-card transition-transform duration-200 ease-clinical group-hover:scale-105">
            <Activity className="h-4.5 w-4.5" aria-hidden />
          </span>
          <span className="truncate text-lg font-semibold tracking-tight text-foreground">
            {t.appName}
          </span>
          {role && (
            <Badge tone="primary" className="ml-1 hidden sm:inline-flex">
              {role === "doctor" ? t.roles.doctor : t.roles.reception}
            </Badge>
          )}
        </Link>

        <div className="flex shrink-0 items-center gap-1.5 sm:gap-2.5">
          {actions}
          <ThemeToggle />
          <LanguageSwitcher />
          {user && (
            <span
              className="hidden max-w-[10rem] truncate text-sm text-muted lg:inline"
              title={user.name}
            >
              {user.name}
            </span>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={logout}
            aria-label={t.common.signOut}
          >
            <LogOut className="h-4 w-4" aria-hidden />
            <span className="hidden sm:inline">{t.common.signOut}</span>
          </Button>
        </div>
      </div>
    </header>
  );
}
