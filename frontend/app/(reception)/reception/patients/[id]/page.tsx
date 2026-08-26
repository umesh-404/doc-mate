"use client";

import {
  AlertTriangle,
  ArrowLeft,
  CloudOff,
  FileStack,
  Loader2,
  Stethoscope,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { CacheNotice } from "@/components/offline/CacheNotice";
import { OfflineUnavailable } from "@/components/offline/OfflineUnavailable";
import { DocumentVerifyCard } from "@/components/reception/DocumentVerifyCard";
import { RequireRole } from "@/components/RequireRole";
import { UploadDropzone } from "@/components/UploadDropzone";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { SelectField } from "@/components/ui/Input";
import { Skeleton, SkeletonDocList } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { useI18n } from "@/lib/i18n";
import type { UploadDocumentPayload } from "@/lib/offline/outbox";
import { useOffline, usePendingFor } from "@/lib/offline/provider";
import { qk, useDocuments, usePatient, useUploadDocument } from "@/lib/queries";
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
  const { online } = useOffline();
  const { documents: queuedDocs } = usePendingFor(patientId);

  const [docType, setDocType] = useState<string>(DOC_TYPES[0]!.value);

  function onUpload(files: File[]) {
    for (const file of files) {
      upload.mutate({ file, docType });
    }
  }

  const docs = documents.data ?? [];

  return (
    <RequireRole role="reception">
      <div className="mb-4 flex items-center justify-between gap-3">
        <Link
          href="/reception/patients"
          className="inline-flex items-center gap-1.5 rounded-md py-1 text-sm font-medium text-muted transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden />
          {t.nav.patients}
        </Link>
        <Link href={`/doctor/patients/${patientId}`}>
          <Button variant="secondary" size="sm">
            <Stethoscope className="h-3.5 w-3.5" aria-hidden />
            {t.docs.openSnapshot}
          </Button>
        </Link>
      </div>

      {/* Patient identity */}
      <CacheNotice
        className="mb-3"
        queryKey={qk.patient(patientId)}
        stale={patient.isError && !!patient.data}
      />

      {!online && !patient.data ? (
        <OfflineUnavailable className="mb-5" />
      ) : patient.isLoading && !patient.data ? (
        <div
          className="mb-5 rounded-lg border border-border bg-surface p-5 shadow-card"
          role="status"
          aria-busy="true"
        >
          <span className="sr-only">{t.states.loading}</span>
          <Skeleton className="h-7 w-56" />
          <Skeleton className="mt-2 h-3.5 w-80 max-w-full" />
        </div>
      ) : patient.isError && !patient.data ? (
        <ErrorState
          className="mb-5"
          title={t.patients.loadError}
          body={t.states.errorBody}
          onRetry={() => void patient.refetch()}
          retryLabel={t.common.retry}
        />
      ) : patient.data ? (
        <div className="mb-5 animate-rise-in rounded-lg border border-border bg-surface p-4 shadow-card sm:p-5">
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">
              {patient.data.full_name}
            </h1>
            <Badge tone="outline" className="font-mono">
              {patient.data.id}
            </Badge>
          </div>
          <p className="mt-1 text-sm text-muted text-pretty">
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

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        {/* Upload */}
        <div className="lg:col-span-1">
          <Card className="lg:sticky lg:top-20">
            <CardHeader>
              <CardTitle>{t.docs.uploadTitle}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <SelectField
                id="docType"
                label={t.docs.docType}
                value={docType}
                onChange={(e) => setDocType(e.target.value)}
              >
                {DOC_TYPES.map((d) => (
                  <option key={d.value} value={d.value}>
                    {t.docs.types[d.labelKey as keyof typeof t.docs.types]}
                  </option>
                ))}
              </SelectField>

              <UploadDropzone onUpload={onUpload} busy={upload.isPending} />

              <div aria-live="polite" className="min-h-[1rem]">
                {upload.isPending && (
                  <p className="flex items-center gap-1.5 text-xs font-medium text-primary">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                    {t.docs.uploading}
                  </p>
                )}
                {/* Offline uploads succeed locally, not on the server. Say
                    which one happened (PROJECT.md §4 rule 5). */}
                {!upload.isPending && upload.data?.queued && (
                  <p className="flex items-center gap-1.5 text-xs font-medium text-warning">
                    <CloudOff className="h-3.5 w-3.5" aria-hidden />
                    {t.offline.savedLocally}
                  </p>
                )}
                {upload.isError && (
                  <p
                    role="alert"
                    className="flex items-center gap-1.5 text-xs font-medium text-danger"
                  >
                    <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
                    {t.docs.uploadError}
                  </p>
                )}
              </div>

              <p className="border-t border-border pt-3 text-xs leading-relaxed text-muted">
                {t.newPatient.verifyNote}
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Documents + verify */}
        <div className="lg:col-span-2">
          <div className="mb-2.5 flex items-center gap-2">
            <h2 className="text-2xs font-bold uppercase tracking-[0.09em] text-muted">
              {t.docs.documentsTitle}
            </h2>
            {docs.length > 0 && (
              <span className="rounded-full bg-surface-muted px-1.5 py-px text-2xs font-semibold tabular-nums text-muted">
                {docs.length}
              </span>
            )}
          </div>

          <CacheNotice
            className="mb-2.5"
            queryKey={qk.documents(patientId)}
            stale={documents.isError && !!documents.data}
          />

          {/* Files captured offline. They are real bytes held on this device,
              but the ingestion pipeline has not seen them yet — so they get a
              queued badge, not a processing status. */}
          {queuedDocs.length > 0 && (
            <ul className="mb-3 flex flex-col gap-2">
              {queuedDocs.map((item) => {
                const payload = item.payload as UploadDocumentPayload;
                const attention =
                  item.state === "failed" || item.state === "conflict";
                return (
                  <li
                    key={item.id}
                    className={`flex items-center justify-between gap-3 rounded-lg border px-3.5 py-3 ${
                      attention
                        ? "border-danger/40 bg-danger-surface/50"
                        : "border-warning/45 bg-warning-surface/40"
                    }`}
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-foreground">
                        {payload.filename}
                      </p>
                      <p className="text-xs text-muted">
                        {t.offline.notSyncedYet}
                      </p>
                    </div>
                    <Badge tone={attention ? "danger" : "warning"}>
                      <CloudOff className="h-3 w-3" aria-hidden />
                      {attention ? t.offline.attentionTitle : t.offline.queued}
                    </Badge>
                  </li>
                );
              })}
            </ul>
          )}

          {!online && !documents.data && queuedDocs.length === 0 ? (
            <OfflineUnavailable />
          ) : documents.isLoading && !documents.data ? (
            <SkeletonDocList label={t.states.loading} />
          ) : documents.isError && !documents.data ? (
            <ErrorState
              title={t.states.errorTitle}
              body={t.states.errorBody}
              onRetry={() => void documents.refetch()}
              retryLabel={t.common.retry}
            />
          ) : docs.length === 0 && queuedDocs.length === 0 ? (
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
