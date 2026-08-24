"use client";

import { ArrowLeft, Loader2, Sparkles } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { RequireRole } from "@/components/RequireRole";
import { PatientSnapshotView } from "@/components/snapshot/PatientSnapshotView";
import { SummaryView } from "@/components/snapshot/SummaryView";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { useI18n } from "@/lib/i18n";
import { getMockSnapshot } from "@/lib/mock-data";
import {
  useGenerateSummary,
  usePatient,
  useSummary,
} from "@/lib/queries";

export default function PatientSnapshotPage({
  params,
}: {
  params: { id: string };
}) {
  const { t } = useI18n();
  const patientId = params.id;

  const [polling, setPolling] = useState(false);
  const [showSample, setShowSample] = useState(false);

  const patient = usePatient(patientId);
  const summary = useSummary(patientId, polling);
  const generate = useGenerateSummary(patientId);

  function onGenerate() {
    generate.mutate(undefined, {
      onSuccess: () => {
        // Poll until the summary is retrievable; the query stops itself once
        // data lands (see the render-time guard below). Covers both the
        // "generating" and immediately-"ready" responses.
        setPolling(true);
        void summary.refetch();
      },
    });
  }

  // Stop polling once the summary lands.
  if (polling && summary.data) setPolling(false);

  const generating = generate.isPending || polling;

  return (
    <RequireRole role="doctor">
      <div className="mb-5 flex items-center justify-between gap-3">
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
    // Patient identity is needed to render the snapshot header.
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
    if (summary.data && patient.data) {
      return <SummaryView summary={summary.data} patient={patient.data} />;
    }

    // Generation in progress.
    if (generating) {
      return (
        <LoadingState label={t.snapshot.generating} />
      );
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
              <p className="mt-1 text-sm text-muted">
                {t.snapshot.generateBody}
              </p>
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
