"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { RequireRole } from "@/components/RequireRole";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { localeNames, locales } from "@/lib/i18n/dictionaries";
import { useCreatePatient } from "@/lib/queries";
import type { NewPatient, Sex } from "@/lib/types";

export default function NewPatientPage() {
  const { t } = useI18n();
  const router = useRouter();
  const createPatient = useCreatePatient();
  const [error, setError] = useState<string | null>(null);

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    const form = new FormData(e.currentTarget);

    const fullName = String(form.get("fullName") ?? "").trim();
    if (!fullName) return;

    const ageRaw = String(form.get("age") ?? "").trim();
    const abha = String(form.get("abhaId") ?? "").trim();
    const phone = String(form.get("phone") ?? "").trim();

    const body: NewPatient = {
      full_name: fullName,
      sex: (String(form.get("sex") ?? "M") as Sex) || undefined,
      preferred_language: String(form.get("lang") ?? "en"),
    };
    if (ageRaw) {
      const n = Number(ageRaw);
      if (!Number.isNaN(n)) body.age = n;
    }
    if (abha) body.abha_id = abha;
    if (phone) body.phone = phone;

    createPatient.mutate(body, {
      onSuccess: (patient) => {
        router.push(`/reception/patients/${patient.id}`);
      },
      onError: (err) => {
        setError(err instanceof ApiError ? err.message : t.newPatient.createError);
      },
    });
  }

  const submitting = createPatient.isPending;

  return (
    <RequireRole role="reception">
      <div className="mb-6 flex items-center gap-3">
        <Link
          href="/reception/patients"
          className="inline-flex items-center gap-1 text-sm text-muted hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          {t.common.back}
        </Link>
      </div>

      <h1 className="text-2xl font-semibold tracking-tight">
        {t.nav.newPatient}
      </h1>
      <p className="mb-6 text-sm text-muted">{t.newPatient.intro}</p>

      <form onSubmit={onSubmit} className="grid gap-6 lg:grid-cols-3">
        <div className="flex flex-col gap-6 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>{t.newPatient.detailsTitle}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 sm:grid-cols-2">
                <Input name="fullName" label={t.newPatient.fullName} required />
                <Input
                  name="abhaId"
                  label={t.newPatient.abhaId}
                  placeholder={t.newPatient.abhaHint}
                />
                <Input
                  name="age"
                  label={t.newPatient.age}
                  type="number"
                  min={0}
                  max={130}
                />
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="sex" className="text-sm font-medium">
                    {t.newPatient.sex}
                  </label>
                  <select
                    id="sex"
                    name="sex"
                    className="h-10 rounded-md border border-border bg-surface px-3 text-sm focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
                    defaultValue="M"
                  >
                    <option value="M">{t.newPatient.male}</option>
                    <option value="F">{t.newPatient.female}</option>
                    <option value="O">{t.newPatient.other}</option>
                  </select>
                </div>
                <Input name="phone" label={t.newPatient.phone} type="tel" />
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="lang" className="text-sm font-medium">
                    {t.newPatient.preferredLanguage}
                  </label>
                  <select
                    id="lang"
                    name="lang"
                    className="h-10 rounded-md border border-border bg-surface px-3 text-sm focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
                    defaultValue="en"
                  >
                    {locales.map((l) => (
                      <option key={l} value={l}>
                        {localeNames[l]}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-1">
          <Card className="lg:sticky lg:top-20">
            <CardHeader>
              <CardTitle>{t.newPatient.summaryTitle}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3 text-sm">
              <p className="text-xs leading-relaxed text-muted">
                {t.newPatient.verifyNote}
              </p>
              {error && (
                <p
                  role="alert"
                  className="rounded-md border border-danger/30 bg-danger-surface px-3 py-2 text-sm text-danger"
                >
                  {error}
                </p>
              )}
              <Button
                type="submit"
                size="lg"
                className="mt-2 w-full"
                disabled={submitting}
              >
                {submitting ? t.newPatient.creating : t.newPatient.create}
              </Button>
            </CardContent>
          </Card>
        </div>
      </form>
    </RequireRole>
  );
}
