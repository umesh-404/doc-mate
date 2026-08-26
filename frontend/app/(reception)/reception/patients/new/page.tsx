"use client";

import {
  ArrowLeft,
  BadgeCheck,
  CloudOff,
  Loader2,
  Search,
  UserPlus,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { RequireRole } from "@/components/RequireRole";
import { VoiceCapture } from "@/components/VoiceCapture";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Input, SelectField, Textarea } from "@/components/ui/Input";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { localeNames, locales } from "@/lib/i18n/dictionaries";
import { useOffline } from "@/lib/offline/provider";
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
  const { online } = useOffline();
  const [error, setError] = useState<string | null>(null);

  // Controlled fields so ABHA lookup + voice intake can prefill them.
  const [fullName, setFullName] = useState("");
  const [abhaId, setAbhaId] = useState("");
  const [age, setAge] = useState("");
  const [sex, setSex] = useState<Sex>("M");
  const [phone, setPhone] = useState("");
  const [lang, setLang] = useState<string>("en");
  const [note, setNote] = useState("");

  // Inline validation is shown only after a submit attempt so the form does
  // not scold the user mid-typing.
  const [touched, setTouched] = useState(false);

  const [looking, setLooking] = useState(false);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [lookupVerified, setLookupVerified] = useState<boolean | null>(null);

  const nameError =
    touched && !fullName.trim() ? t.newPatient.nameRequired : null;
  const ageValue = age.trim() ? Number(age.trim()) : null;
  const ageError =
    touched &&
    ageValue !== null &&
    (Number.isNaN(ageValue) || ageValue < 0 || ageValue > 130)
      ? t.newPatient.ageInvalid
      : null;

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
    setTouched(true);
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
      onSuccess: (result) => {
        if (result.queued) {
          // Offline: the registration is safe on this device but the server has
          // not issued an id, so there is no patient page to open yet. Return to
          // the list, where it shows as queued until it syncs.
          router.push("/reception/patients");
          return;
        }
        router.push(`/reception/patients/${result.data.id}`);
      },
      onError: (err) => {
        setError(
          err instanceof ApiError ? err.message : t.newPatient.createError,
        );
      },
    });
  }

  const submitting = createPatient.isPending;

  return (
    <RequireRole role="reception">
      <div className="mb-4 flex items-center gap-3">
        <Link
          href="/reception/patients"
          className="inline-flex items-center gap-1.5 rounded-md py-1 text-sm font-medium text-muted transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden />
          {t.common.back}
        </Link>
      </div>

      <div className="mb-5">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          {t.nav.newPatient}
        </h1>
        <p className="mt-1 max-w-2xl text-sm leading-relaxed text-muted text-pretty">
          {t.newPatient.intro}
        </p>
      </div>

      <form onSubmit={onSubmit} noValidate className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="flex flex-col gap-5 lg:col-span-2">
          {/* ABHA lookup */}
          <Card>
            <CardHeader>
              <CardTitle>{t.abha.title}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <p className="text-xs leading-relaxed text-muted text-pretty">
                {t.abha.hint}
              </p>
              <div className="flex flex-wrap items-end gap-3">
                <div className="min-w-[200px] flex-1">
                  <Input
                    name="abhaId"
                    label={t.newPatient.abhaId}
                    placeholder={t.abha.placeholder}
                    inputMode="numeric"
                    autoComplete="off"
                    className="font-mono"
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
              <div aria-live="polite" className="empty:hidden">
                {lookupVerified !== null && (
                  <div className="flex animate-rise-in flex-wrap items-center gap-2 text-xs">
                    <Badge tone={lookupVerified ? "success" : "warning"}>
                      <BadgeCheck className="h-3 w-3" aria-hidden />
                      {lookupVerified ? t.abha.verified : t.abha.unverified}
                    </Badge>
                    <span className="text-muted">{t.abha.prefilled}</span>
                  </div>
                )}
                {lookupError && (
                  <p role="alert" className="text-xs font-medium text-danger">
                    {lookupError}
                  </p>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Identity */}
          <Card>
            <CardHeader>
              <CardTitle>{t.newPatient.detailsTitle}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-5">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="sm:col-span-2">
                  <Input
                    name="fullName"
                    label={t.newPatient.fullName}
                    required
                    autoComplete="off"
                    error={nameError}
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                  />
                </div>
                <Input
                  name="age"
                  label={t.newPatient.age}
                  type="number"
                  inputMode="numeric"
                  min={0}
                  max={130}
                  error={ageError}
                  value={age}
                  onChange={(e) => setAge(e.target.value)}
                />
                <SelectField
                  id="sex"
                  name="sex"
                  label={t.newPatient.sex}
                  value={sex}
                  onChange={(e) => setSex(e.target.value as Sex)}
                >
                  <option value="M">{t.newPatient.male}</option>
                  <option value="F">{t.newPatient.female}</option>
                  <option value="O">{t.newPatient.other}</option>
                </SelectField>
                <Input
                  name="phone"
                  label={t.newPatient.phone}
                  type="tel"
                  inputMode="tel"
                  autoComplete="off"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                />
                <SelectField
                  id="lang"
                  name="lang"
                  label={t.newPatient.preferredLanguage}
                  value={lang}
                  onChange={(e) => setLang(e.target.value)}
                >
                  {locales.map((l) => (
                    <option key={l} value={l}>
                      {localeNames[l]}
                    </option>
                  ))}
                </SelectField>
              </div>

              {/* Reason for visit / intake note with voice capture */}
              <div className="flex flex-col gap-1.5 border-t border-border pt-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <label
                    htmlFor="note"
                    className="text-xs font-semibold text-foreground-subtle"
                  >
                    {t.newPatient.note}
                  </label>
                  <VoiceCapture
                    lang={lang}
                    onTranscribed={(text) =>
                      setNote((prev) => (prev ? `${prev} ${text}` : text))
                    }
                  />
                </div>
                <Textarea
                  id="note"
                  name="note"
                  rows={3}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder={t.newPatient.notePlaceholder}
                />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Review + submit */}
        <div className="lg:col-span-1">
          <Card className="lg:sticky lg:top-20">
            <CardHeader>
              <CardTitle>{t.newPatient.summaryTitle}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <dl className="flex flex-col divide-y divide-border text-sm">
                <ReviewRow
                  label={t.newPatient.fullName}
                  value={fullName.trim()}
                />
                <ReviewRow label={t.newPatient.age} value={age.trim()} />
                <ReviewRow
                  label={t.newPatient.sex}
                  value={
                    sex === "M"
                      ? t.newPatient.male
                      : sex === "F"
                        ? t.newPatient.female
                        : t.newPatient.other
                  }
                />
                <ReviewRow label={t.newPatient.abhaId} value={abhaId.trim()} />
                <ReviewRow
                  label={t.newPatient.preferredLanguage}
                  value={
                    localeNames[lang as keyof typeof localeNames] ?? lang
                  }
                />
              </dl>

              <p className="text-xs leading-relaxed text-muted text-pretty">
                {t.newPatient.verifyNote}
              </p>

              {/* Say up front what will happen to this registration offline,
                  so "Create patient" never implies it reached the server. */}
              {!online && (
                <p
                  role="note"
                  className="flex items-start gap-1.5 rounded-md border border-warning/45 bg-warning-surface px-3 py-2 text-xs font-medium leading-relaxed text-warning"
                >
                  <CloudOff className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                  {t.offline.queued} — {t.offline.savedLocally}
                </p>
              )}

              <div aria-live="polite" className="empty:hidden">
                {error && (
                  <p
                    role="alert"
                    className="rounded-md border border-danger/35 bg-danger-surface px-3 py-2 text-sm font-medium text-danger"
                  >
                    {error}
                  </p>
                )}
              </div>

              <Button
                type="submit"
                size="lg"
                className="w-full"
                disabled={submitting}
              >
                {submitting ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                ) : (
                  <UserPlus className="h-4 w-4" aria-hidden />
                )}
                {submitting ? t.newPatient.creating : t.newPatient.create}
              </Button>
            </CardContent>
          </Card>
        </div>
      </form>
    </RequireRole>
  );
}

/** One line of the live review panel; empty values read as an em dash. */
function ReviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1.5 first:pt-0">
      <dt className="shrink-0 text-xs text-muted">{label}</dt>
      <dd
        className={
          value
            ? "min-w-0 truncate text-right text-sm font-medium text-foreground"
            : "text-sm text-muted"
        }
      >
        {value || "—"}
      </dd>
    </div>
  );
}
