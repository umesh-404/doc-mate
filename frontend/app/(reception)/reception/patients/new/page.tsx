"use client";

import { ArrowLeft, CheckCircle2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { RequireRole } from "@/components/RequireRole";
import { UploadDropzone, type StagedFile } from "@/components/UploadDropzone";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { useI18n } from "@/lib/i18n";
import { localeNames, locales } from "@/lib/i18n/dictionaries";

export default function NewPatientPage() {
  const { t } = useI18n();
  const [files, setFiles] = useState<StagedFile[]>([]);
  const [submitted, setSubmitted] = useState(false);
  const [notes, setNotes] = useState("");

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    // UI only: in the real flow this creates the patient/encounter and POSTs
    // each staged file to the ingestion endpoint. We just acknowledge here.
    setSubmitted(true);
  }

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
      <p className="mb-6 text-sm text-muted">
        Enter what you know and upload everything available. The system ingests
        and indexes it for the doctor.
      </p>

      {submitted && (
        <div
          role="status"
          className="mb-6 flex items-center gap-2 rounded-md border border-success/30 bg-success-surface px-4 py-3 text-sm text-success"
        >
          <CheckCircle2 className="h-4 w-4" aria-hidden />
          Patient registered and {files.length} file(s) queued for processing
          (demo — no data sent).
        </div>
      )}

      <form onSubmit={onSubmit} className="grid gap-6 lg:grid-cols-3">
        <div className="flex flex-col gap-6 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>Patient details</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 sm:grid-cols-2">
                <Input name="fullName" label="Full name" required />
                <Input name="abhaId" label="ABHA ID" placeholder="14-digit" />
                <Input name="age" label="Age" type="number" min={0} max={130} />
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="sex" className="text-sm font-medium">
                    Sex
                  </label>
                  <select
                    id="sex"
                    name="sex"
                    className="h-10 rounded-md border border-border bg-surface px-3 text-sm focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
                    defaultValue="M"
                  >
                    <option value="M">Male</option>
                    <option value="F">Female</option>
                    <option value="O">Other</option>
                  </select>
                </div>
                <Input name="phone" label="Phone" type="tel" />
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="lang" className="text-sm font-medium">
                    Preferred language
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

          <Card>
            <CardHeader>
              <CardTitle>Reason for visit / typed notes</CardTitle>
            </CardHeader>
            <CardContent>
              <textarea
                name="notes"
                rows={4}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Current complaint, history, anything the patient tells you…"
                className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Upload records</CardTitle>
            </CardHeader>
            <CardContent>
              <UploadDropzone files={files} onChange={setFiles} />
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-1">
          <Card className="lg:sticky lg:top-20">
            <CardHeader>
              <CardTitle>Summary</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-muted">Files staged</span>
                <span className="font-medium">{files.length}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted">Typed notes</span>
                <span className="font-medium">
                  {notes.trim() ? "Yes" : "—"}
                </span>
              </div>
              <p className="text-xs leading-relaxed text-muted">
                Extracted fields (medications, doses, labs) are shown as
                <em> proposed</em> and verified here before the doctor sees them.
              </p>
              <Button type="submit" size="lg" className="mt-2 w-full">
                Register &amp; queue for processing
              </Button>
            </CardContent>
          </Card>
        </div>
      </form>
    </RequireRole>
  );
}
