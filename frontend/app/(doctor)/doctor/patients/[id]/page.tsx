"use client";

import { ArrowLeft, Loader2, Sparkles } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { RequireRole } from "@/components/RequireRole";
import { PatientSnapshotView } from "@/components/snapshot/PatientSnapshotView";
import { PlainLanguagePanel } from "@/components/snapshot/PlainLanguagePanel";
import { SnapshotToolbar, SUMMARY_LANGS } from "@/components/snapshot/SnapshotToolbar";
import { SummaryView } from "@/components/snapshot/SummaryView";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { api, ApiError, type SummaryLang } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { getMockSnapshot } from "@/lib/mock-data";
import {
  useGenerateSummary,
  useInteractions,
  usePatient,
  usePatientCodes,
  usePlainSummary,
  useSummary,
  useTranslatedSummary,
} from "@/lib/queries";

function asSummaryLang(value: string | undefined): SummaryLang {
  return (SUMMARY_LANGS as string[]).includes(value ?? "")
    ? (value as SummaryLang)
    : "en";
}

export default function PatientSnapshotPage({
  params,
}: {
  params: { id: string };
}) {
  const { t } = useI18n();
  const patientId = params.id;

  const [polling, setPolling] = useState(false);
  const [showSample, setShowSample] = useState(false);
  const [viewLang, setViewLang] = useState<SummaryLang | null>(null);
  const [plainOpen, setPlainOpen] = useState(false);
  const [exportingFhir, setExportingFhir] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const patient = usePatient(patientId);
  const summary = useSummary(patientId, polling);
  const generate = useGenerateSummary(patientId);

  const baseSummary = summary.data ?? null;
  const baseLang = asSummaryLang(baseSummary?.language);
  const activeLang = viewLang ?? baseLang;
  const needTranslate = !!baseSummary && activeLang !== baseLang;

  // Ancillary contract-v2 data — only once a base summary exists.
  const hasSummary = !!baseSummary;
  const translated = useTranslatedSummary(patientId, activeLang, needTranslate);
  const plain = usePlainSummary(patientId, activeLang, plainOpen && hasSummary);
  const interactions = useInteractions(patientId, hasSummary);
  const codes = usePatientCodes(patientId, hasSummary);

  const displaySummary = needTranslate
    ? (translated.data ?? baseSummary)
    : baseSummary;

  function onGenerate() {
    generate.mutate(undefined, {
      onSuccess: () => {
        setPolling(true);
        void summary.refetch();
      },
    });
  }

  async function onExportFhir() {
    setExportError(null);
    setExportingFhir(true);
    try {
      const blob = await api.fhirBundleBlob(patientId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `patient-${patientId}-fhir-bundle.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(err instanceof ApiError ? err.message : t.common.error);
    } finally {
      setExportingFhir(false);
    }
  }

  // Stop polling once the summary lands.
  if (polling && summary.data) setPolling(false);

  const generating = generate.isPending || polling;

  return (
    <RequireRole role="doctor">
      <div className="mb-5 flex items-center justify-between gap-3 print:hidden">
        <Link
          href="/doctor/patients"
          className="inline-flex items-center gap-1 text-sm text-muted hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          {t.nav.patients}
        </Link>
        <span className="text-sm font-medium text-muted">{t.snapshot.title}</span>
      </div>

      {renderBody()}
    </RequireRole>
  );

  function renderBody() {
    if (patient.isError) {
      return (
        <ErrorState
          title={t.patients.loadError}
          body={t.states.errorBody}
          onRetry={() => void patient.refetch()}
          retryLabel={t.common.retry}
        />
      );
    }

    if (summary.isError) {
      return (
        <ErrorState
          title={t.snapshot.loadError}
          body={t.states.errorBody}
          onRetry={() => void summary.refetch()}
          retryLabel={t.common.retry}
        />
      );
    }

    if (patient.isLoading || summary.isLoading) {
      return <LoadingState label={t.states.loading} />;
    }

    // Real summary available — the primary path.
    if (displaySummary && patient.data) {
      return (
        <div className="flex flex-col gap-5">
          <SnapshotToolbar
            lang={activeLang}
            onLang={setViewLang}
            translating={needTranslate && translated.isFetching}
            plainOpen={plainOpen}
            onTogglePlain={() => setPlainOpen((v) => !v)}
            onExportFhir={onExportFhir}
            exportingFhir={exportingFhir}
            onPrint={() => window.print()}
          />
          {exportError && (
            <p className="rounded-md border border-danger/30 bg-danger-surface px-3 py-2 text-sm text-danger print:hidden">
              {exportError}
            </p>
          )}
          {plainOpen && (
            <PlainLanguagePanel
              plain={plain.data}
              loading={plain.isLoading}
              error={plain.isError}
            />
          )}
          <SummaryView
            summary={displaySummary}
            patient={patient.data}
            codes={codes.data}
            interactions={interactions.data}
          />
        </div>
      );
    }

    // Generation in progress.
    if (generating) {
      return <LoadingState label={t.snapshot.generating} />;
    }

    // No summary yet (404) — offer to generate, with an optional sample preview.
    return (
      <div className="flex flex-col gap-5">
        <Card>
          <CardContent className="flex flex-col items-center gap-4 py-12 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
              <Sparkles className="h-6 w-6" aria-hidden />
            </span>
            <div className="max-w-md">
              <h2 className="text-lg font-semibold text-foreground">
                {t.snapshot.generateTitle}
              </h2>
              <p className="mt-1 text-sm text-muted">{t.snapshot.generateBody}</p>
            </div>
            <Button size="lg" onClick={onGenerate} disabled={generate.isPending}>
              {generate.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              ) : (
                <Sparkles className="h-4 w-4" aria-hidden />
              )}
              {t.snapshot.generateAction}
            </Button>
            {generate.isError && (
              <p className="text-sm text-danger">{t.common.error}</p>
            )}
            <button
              type="button"
              onClick={() => setShowSample((v) => !v)}
              className="text-xs font-medium text-primary hover:underline"
            >
              {showSample ? t.snapshot.hideSample : t.snapshot.viewSample}
            </button>
          </CardContent>
        </Card>

        {showSample && (
          <div className="flex flex-col gap-3">
            <p className="rounded-md border border-warning/30 bg-warning-surface/50 px-3 py-2 text-xs font-medium text-warning">
              {t.snapshot.sampleBanner}
            </p>
            <PatientSnapshotView data={getMockSnapshot(patientId)} />
          </div>
        )}
      </div>
    );
  }
}
