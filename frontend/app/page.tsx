"use client";

import { Activity, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
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
        resolvedRole === "doctor"
          ? "/doctor/patients"
          : "/reception/patients",
      );
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : t.login.failed;
      setError(msg || t.login.failed);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Brand / value panel */}
      <div className="relative hidden flex-col justify-between bg-primary p-10 text-primary-foreground lg:flex">
        <div className="flex items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-md bg-white/15">
            <Activity className="h-5 w-5" aria-hidden />
          </span>
          <span className="text-xl font-semibold">{t.appName}</span>
        </div>
        <div className="max-w-md">
          <h1 className="text-3xl font-semibold leading-tight text-balance">
            {t.tagline}
          </h1>
          <p className="mt-4 text-sm leading-relaxed text-white/80">
            Reception uploads everything about a patient. The doctor opens a
            fast, citation-backed snapshot and spends the visit on care — not
            paperwork.
          </p>
          <div className="mt-6 flex items-center gap-2 text-sm text-white/80">
            <ShieldCheck className="h-4 w-4" aria-hidden />
            Summarises and cites. Never diagnoses.
          </div>
        </div>
        <p className="text-xs text-white/60">
          Smart India Hackathon prototype · synthetic demo data
        </p>
      </div>

      {/* Login form */}
      <div className="flex flex-col">
        <div className="flex justify-end p-4">
          <LanguageSwitcher />
        </div>
        <div className="flex flex-1 items-center justify-center px-6 pb-16">
          <form onSubmit={onSubmit} className="w-full max-w-sm">
            <div className="mb-6 flex items-center gap-2 lg:hidden">
              <span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
                <Activity className="h-5 w-5" aria-hidden />
              </span>
              <span className="text-lg font-semibold">{t.appName}</span>
            </div>

            <h2 className="text-2xl font-semibold tracking-tight">
              {t.login.heading}
            </h2>
            <p className="mt-1 text-sm text-muted">{t.login.subheading}</p>

            <div className="mt-6 flex flex-col gap-4">
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

              {error && (
                <p
                  role="alert"
                  className="rounded-md border border-danger/30 bg-danger-surface px-3 py-2 text-sm text-danger"
                >
                  {error}
                </p>
              )}

              <Button type="submit" size="lg" disabled={submitting}>
                {submitting ? t.common.loading : t.common.signIn}
              </Button>

              <p className="text-center text-xs text-muted">
                {t.login.demoHint}
              </p>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
