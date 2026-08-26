"use client";

import { ArrowLeft, BadgeCheck, Loader2, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { RequireRole } from "@/components/RequireRole";
import { VoiceCapture } from "@/components/VoiceCapture";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { localeNames, locales } from "@/lib/i18n/dictionaries";
import { useCreatePatient } from "@/lib/queries";
import type { NewPatient, Sex } from "@/lib/types";

function genderToSex(gender: string): Sex {
  const g = gender.trim().toLowerCase();
  if (g.startsWith("m")) return "M";
  if (g.startsWith("f")) return "F";
  return "O";
}

export default function NewPatientPage() {
  const { t } = useI18n();
  const router = useRouter();
  const createPatient = useCreatePatient();
  const [error, setError] = useState<string | null>(null);

  // Controlled fields so ABHA lookup + voice intake can prefill them.
  const [fullName, setFullName] = useState("");
  const [abhaId, setAbhaId] = useState("");
  const [age, setAge] = useState("");
  const [sex, setSex] = useState<Sex>("M");
  const [phone, setPhone] = useState("");
  const [lang, setLang] = useState<string>("en");
  const [note, setNote] = useState("");

  const [looking, setLooking] = useState(false);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [lookupVerified, setLookupVerified] = useState<boolean | null>(null);

  async function onAbhaLookup() {
    const id = abhaId.trim();
    if (!id) return;
    setLookupError(null);
    setLookupVerified(null);
    setLooking(true);
    try {
      const res = await api.abhaLookup(id);
      setFullName(res.name);
      setSex(genderToSex(res.gender));
      if (res.year_of_birth) {
        const derived = new Date().getFullYear() - res.year_of_birth;
        if (derived > 0 && derived < 130) setAge(String(derived));
      }
      setLookupVerified(res.verified);
    } catch (err) {
      setLookupError(err instanceof ApiError ? err.message : t.abha.error);
    } finally {
      setLooking(false);
    }
  }

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    if (!fullName.trim()) return;

    const body: NewPatient = {
      full_name: fullName.trim(),
      sex,
      preferred_language: lang,
    };
    if (age.trim()) {
      const n = Number(age.trim());
      if (!Number.isNaN(n)) body.age = n;
    }
    if (abhaId.trim()) body.abha_id = abhaId.trim();
    if (phone.trim()) body.phone = phone.trim();
    if (note.trim()) body.note = note.trim();

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
          {/* ABHA lookup */}
          <Card>
            <CardHeader>
              <CardTitle>{t.abha.title}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <p className="text-xs leading-relaxed text-muted">{t.abha.hint}</p>
              <div className="flex flex-wrap items-end gap-3">
                <div className="min-w-[200px] flex-1">
                  <Input
                    name="abhaId"
                    label={t.newPatient.abhaId}
                    placeholder={t.abha.placeholder}
                    value={abhaId}
                    onChange={(e) => setAbhaId(e.target.value)}
                  />
                </div>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={onAbhaLookup}
                  disabled={looking || !abhaId.trim()}
                >
                  {looking ? (
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                  ) : (
                    <Search className="h-4 w-4" aria-hidden />
                  )}
                  {t.abha.lookup}
                </Button>
              </div>
              {lookupVerified !== null && (
                <div className="flex items-center gap-2 text-xs">
                  <Badge tone={lookupVerified ? "success" : "warning"}>
                    <BadgeCheck className="h-3 w-3" aria-hidden />
                    {lookupVerified ? t.abha.verified : t.abha.unverified}
                  </Badge>
                  <span className="text-muted">{t.abha.prefilled}</span>
                </div>
              )}
              {lookupError && (
                <p className="text-xs text-danger">{lookupError}</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t.newPatient.detailsTitle}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 sm:grid-cols-2">
                <Input
                  name="fullName"
                  label={t.newPatient.fullName}
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                />
                <Input
                  name="age"
                  label={t.newPatient.age}
                  type="number"
                  min={0}
                  max={130}
                  value={age}
                  onChange={(e) => setAge(e.target.value)}
                />
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="sex" className="text-sm font-medium">
                    {t.newPatient.sex}
                  </label>
                  <select
                    id="sex"
                    name="sex"
                    className="h-10 rounded-md border border-border bg-surface px-3 text-sm focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
                    value={sex}
                    onChange={(e) => setSex(e.target.value as Sex)}
                  >
                    <option value="M">{t.newPatient.male}</option>
                    <option value="F">{t.newPatient.female}</option>
                    <option value="O">{t.newPatient.other}</option>
                  </select>
                </div>
                <Input
                  name="phone"
                  label={t.newPatient.phone}
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                />
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="lang" className="text-sm font-medium">
                    {t.newPatient.preferredLanguage}
                  </label>
                  <select
                    id="lang"
                    name="lang"
                    className="h-10 rounded-md border border-border bg-surface px-3 text-sm focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
                    value={lang}
                    onChange={(e) => setLang(e.target.value)}
                  >
                    {locales.map((l) => (
                      <option key={l} value={l}>
                        {localeNames[l]}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Reason for visit / intake note with voice capture */}
              <div className="mt-4 flex flex-col gap-1.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <label htmlFor="note" className="text-sm font-medium">
                    {t.newPatient.note}
                  </label>
                  <VoiceCapture
                    lang={lang}
                    onTranscribed={(text) =>
                      setNote((prev) => (prev ? `${prev} ${text}` : text))
                    }
                  />
                </div>
                <textarea
                  id="note"
                  name="note"
                  rows={3}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder={t.newPatient.notePlaceholder}
                  className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
                />
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
