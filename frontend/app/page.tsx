"use client";

import { Activity, FileSearch, ShieldCheck, Timer } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

export default function LoginPage() {
  const router = useRouter();
  const { login, status, role } = useAuth();
  const { t } = useI18n();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Already signed in? Route to the role home.
  useEffect(() => {
    if (status === "authenticated" && role) {
      router.replace(
        role === "doctor" ? "/doctor/patients" : "/reception/patients",
      );
    }
  }, [status, role, router]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const resolvedRole = await login(email, password);
      router.replace(
        resolvedRole === "doctor" ? "/doctor/patients" : "/reception/patients",
      );
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : t.login.failed;
      setError(msg || t.login.failed);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      {/* Brand / value panel */}
      <div className="relative hidden flex-col justify-between overflow-hidden bg-primary p-10 text-primary-foreground lg:flex">
        {/* Soft clinical gradient wash — no imagery, no noise. */}
        <div
          className="pointer-events-none absolute inset-0 opacity-60"
          style={{
            background:
              "radial-gradient(70% 55% at 15% 0%, hsl(var(--accent) / 0.45), transparent 65%), radial-gradient(55% 45% at 95% 100%, hsl(var(--accent) / 0.28), transparent 60%)",
          }}
          aria-hidden
        />
        <div className="relative flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-md bg-white/15 ring-1 ring-inset ring-white/25">
            <Activity className="h-5 w-5" aria-hidden />
          </span>
          <span className="text-xl font-semibold tracking-tight">
            {t.appName}
          </span>
        </div>

        <div className="relative max-w-md">
          <h1 className="text-3xl font-semibold leading-tight text-balance">
            {t.tagline}
          </h1>
          <p className="mt-4 text-sm leading-relaxed text-primary-foreground/80">
            Reception uploads everything about a patient. The doctor opens a
            fast, citation-backed snapshot and spends the visit on care — not
            paperwork.
          </p>
          <ul className="mt-7 flex flex-col gap-3 text-sm text-primary-foreground/85">
            <li className="flex items-center gap-2.5">
              <Timer className="h-4 w-4 shrink-0 opacity-80" aria-hidden />
              Under a minute to the full patient picture
            </li>
            <li className="flex items-center gap-2.5">
              <FileSearch className="h-4 w-4 shrink-0 opacity-80" aria-hidden />
              Every line links back to its source document
            </li>
            <li className="flex items-center gap-2.5">
              <ShieldCheck className="h-4 w-4 shrink-0 opacity-80" aria-hidden />
              Summarises and cites. Never diagnoses.
            </li>
          </ul>
        </div>

        <p className="relative text-xs text-primary-foreground/60">
          Smart India Hackathon prototype · synthetic demo data
        </p>
      </div>

      {/* Login form */}
      <div className="flex flex-col bg-bg">
        <div className="flex items-center justify-end gap-2 p-4">
          <ThemeToggle />
          <LanguageSwitcher />
        </div>
        <main
          id="main"
          className="flex flex-1 items-center justify-center px-6 pb-16"
        >
          <form onSubmit={onSubmit} className="w-full max-w-sm animate-rise-in">
            <div className="mb-7 flex items-center gap-2.5 lg:hidden">
              <span className="flex h-9 w-9 items-center justify-center rounded-md bg-primary text-primary-foreground shadow-card">
                <Activity className="h-5 w-5" aria-hidden />
              </span>
              <span className="text-lg font-semibold tracking-tight">
                {t.appName}
              </span>
            </div>

            <h1 className="text-2xl font-semibold tracking-tight text-foreground">
              {t.login.heading}
            </h1>
            <p className="mt-1.5 text-sm text-muted">{t.login.subheading}</p>

            <div className="mt-7 flex flex-col gap-4">
              <Input
                name="email"
                type="email"
                label={t.common.email}
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="reception@demo"
              />
              <Input
                name="password"
                type="password"
                label={t.common.password}
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
              />

              <div aria-live="assertive" className="empty:hidden">
                {error && (
                  <p
                    role="alert"
                    className="animate-rise-in rounded-md border border-danger/35 bg-danger-surface px-3 py-2 text-sm font-medium text-danger"
                  >
                    {error}
                  </p>
                )}
              </div>

              <Button type="submit" size="lg" disabled={submitting}>
                {submitting ? t.common.loading : t.common.signIn}
              </Button>

              <p className="rounded-md border border-dashed border-border bg-surface-muted/50 px-3 py-2 text-center text-xs text-muted">
                {t.login.demoHint}
              </p>
            </div>
          </form>
        </main>
      </div>
    </div>
  );
}
