"use client";

import { ArrowLeft, FileStack, Stethoscope } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { DocumentVerifyCard } from "@/components/reception/DocumentVerifyCard";
import { RequireRole } from "@/components/RequireRole";
import { UploadDropzone } from "@/components/UploadDropzone";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { useI18n } from "@/lib/i18n";
import { useDocuments, usePatient, useUploadDocument } from "@/lib/queries";
import { DOC_TYPES } from "@/lib/types";

export default function ReceptionPatientPage({
  params,
}: {
  params: { id: string };
}) {
  const { t } = useI18n();
  const patientId = params.id;

  const patient = usePatient(patientId);
  const documents = useDocuments(patientId);
  const upload = useUploadDocument(patientId);

  const [docType, setDocType] = useState<string>(DOC_TYPES[0]!.value);

  function onUpload(files: File[]) {
    for (const file of files) {
      upload.mutate({ file, docType });
    }
  }

  const docs = documents.data ?? [];

  return (
    <RequireRole role="reception">
      <div className="mb-5 flex items-center justify-between gap-3">
        <Link
          href="/reception/patients"
          className="inline-flex items-center gap-1 text-sm text-muted hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          {t.nav.patients}
        </Link>
        <Link href={`/doctor/patients/${patientId}`}>
          <Button variant="secondary" size="sm">
            <Stethoscope className="h-4 w-4" aria-hidden />
            {t.docs.openSnapshot}
          </Button>
        </Link>
      </div>

      {/* Patient identity */}
      {patient.isLoading ? (
        <LoadingState label={t.states.loading} />
      ) : patient.isError ? (
        <ErrorState
          title={t.patients.loadError}
          body={t.states.errorBody}
          onRetry={() => void patient.refetch()}
          retryLabel={t.common.retry}
        />
      ) : patient.data ? (
        <div className="mb-6 rounded-lg border border-border bg-surface p-5 shadow-card">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">
              {patient.data.full_name}
            </h1>
            <Badge tone="neutral">{patient.data.id}</Badge>
          </div>
          <p className="mt-1 text-sm text-muted">
            {[
              patient.data.age != null ? `${patient.data.age} yrs` : null,
              patient.data.sex,
              patient.data.abha_id ? `ABHA ${patient.data.abha_id}` : null,
              patient.data.preferred_language,
              patient.data.phone,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Upload */}
        <div className="lg:col-span-1">
          <Card className="lg:sticky lg:top-20">
            <CardHeader>
              <CardTitle>{t.docs.uploadTitle}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <label htmlFor="docType" className="text-sm font-medium">
                  {t.docs.docType}
                </label>
                <select
                  id="docType"
                  value={docType}
                  onChange={(e) => setDocType(e.target.value)}
                  className="h-10 rounded-md border border-border bg-surface px-3 text-sm focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
                >
                  {DOC_TYPES.map((d) => (
                    <option key={d.value} value={d.value}>
                      {t.docs.types[d.labelKey as keyof typeof t.docs.types]}
                    </option>
                  ))}
                </select>
              </div>
              <UploadDropzone onUpload={onUpload} busy={upload.isPending} />
              {upload.isPending && (
                <p className="text-xs text-muted">{t.docs.uploading}</p>
              )}
              {upload.isError && (
                <p className="text-xs text-danger">{t.docs.uploadError}</p>
              )}
              <p className="text-xs leading-relaxed text-muted">
                {t.newPatient.verifyNote}
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Documents + verify */}
        <div className="lg:col-span-2">
          <div className="mb-3 flex items-center gap-2">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">
              {t.docs.documentsTitle}
            </h2>
            {docs.length > 0 && (
              <span className="text-xs text-muted">({docs.length})</span>
            )}
          </div>

          {documents.isLoading ? (
            <LoadingState label={t.states.loading} />
          ) : documents.isError ? (
            <ErrorState
              title={t.states.errorTitle}
              body={t.states.errorBody}
              onRetry={() => void documents.refetch()}
              retryLabel={t.common.retry}
            />
          ) : docs.length === 0 ? (
            <EmptyState
              icon={<FileStack className="h-5 w-5" aria-hidden />}
              title={t.docs.noDocuments}
              body={t.docs.uploadTitle}
            />
          ) : (
            <ul className="flex flex-col gap-3">
              {docs.map((d) => (
                <DocumentVerifyCard
                  key={d.id}
                  document={d}
                  patientId={patientId}
                />
              ))}
            </ul>
          )}
        </div>
      </div>
    </RequireRole>
  );
}
