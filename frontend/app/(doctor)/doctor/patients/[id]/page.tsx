"use client";

import { ArrowLeft, Loader2, Sparkles } from "lucide-react";
import Link from "next/link";
import { useCallback, useRef, useState } from "react";
import { RequireRole } from "@/components/RequireRole";
import { ShortcutsHelp, ShortcutsHint } from "@/components/ShortcutsHelp";
import { PatientSnapshotView } from "@/components/snapshot/PatientSnapshotView";
import { PlainLanguagePanel } from "@/components/snapshot/PlainLanguagePanel";
import {
  SnapshotToolbar,
  SUMMARY_LANGS,
} from "@/components/snapshot/SnapshotToolbar";
import { SummaryView } from "@/components/snapshot/SummaryView";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { SnapshotSkeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import { api, ApiError, type SummaryLang } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { getMockSnapshot } from "@/lib/mock-data";
import { useShortcuts } from "@/lib/shortcuts";
import { useTheme } from "@/lib/theme";
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
  const { cycleTheme } = useTheme();
  const patientId = params.id;

  const [polling, setPolling] = useState(false);
  const [showSample, setShowSample] = useState(false);
  const [viewLang, setViewLang] = useState<SummaryLang | null>(null);
  const [plainOpen, setPlainOpen] = useState(false);
  const [exportingFhir, setExportingFhir] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [helpOpen, setHelpOpen] = useState(false);

  // Index of the section the j/k navigation is currently parked on.
  const sectionIndex = useRef(-1);

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

  /**
   * Move focus + scroll between snapshot sections. Sections opt in by carrying
   * `data-section`; the DOM is the source of truth so this stays correct no
   * matter which sections the backend returned.
   */
  const moveSection = useCallback((delta: number) => {
    const nodes = Array.from(
      document.querySelectorAll<HTMLElement>("main [data-section]"),
    );
    if (nodes.length === 0) return;
    let next = sectionIndex.current + delta;
    if (next < 0) next = 0;
    if (next > nodes.length - 1) next = nodes.length - 1;
    sectionIndex.current = next;
    const el = nodes[next];
    if (!el) return;
    el.scrollIntoView({ block: "start", behavior: "smooth" });
    el.focus({ preventScroll: true });
  }, []);

  useShortcuts({
    j: () => moveSection(1),
    arrowdown: () => moveSection(1),
    k: () => moveSection(-1),
    arrowup: () => moveSection(-1),
    p: () => window.print(),
    b: () => setPlainOpen((v) => !v),
    t: () => cycleTheme(),
    "?": () => setHelpOpen(true),
    escape: () => setHelpOpen(false),
  });

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
    <RequireRole
      role="doctor"
      headerActions={
        <ShortcutsHint onOpen={() => setHelpOpen(true)} className="hidden sm:inline-flex" />
      }
    >
      <div className="mb-4 flex items-center justify-between gap-3 print:hidden">
        <Link
          href="/doctor/patients"
          className="inline-flex items-center gap-1.5 rounded-md py-1 text-sm font-medium text-muted transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden />
          {t.nav.patients}
        </Link>
        <span className="text-2xs font-semibold uppercase tracking-[0.09em] text-muted">
          {t.snapshot.title}
        </span>
      </div>

      {renderBody()}

      <ShortcutsHelp
        open={helpOpen}
        onClose={() => setHelpOpen(false)}
        entries={[
          { keys: ["j", "↓"], label: t.shortcuts.nextSection },
          { keys: ["k", "↑"], label: t.shortcuts.prevSection },
          { keys: ["b"], label: t.shortcuts.plain },
          { keys: ["p"], label: t.shortcuts.print },
          { keys: ["t"], label: t.shortcuts.theme },
          { keys: ["?"], label: t.shortcuts.help },
        ]}
      />
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
      return <SnapshotSkeleton label={t.states.loading} />;
    }

    // Real summary available — the primary path.
    if (displaySummary && patient.data) {
      return (
        <div className="flex flex-col gap-4">
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
            <p
              role="alert"
              className="rounded-md border border-danger/35 bg-danger-surface px-3 py-2 text-sm font-medium text-danger print:hidden"
            >
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

    // Generation in progress — show the shape of what is coming.
    if (generating) {
      return (
        <div className="flex flex-col gap-4">
          <div
            className="flex items-center gap-2.5 rounded-lg border border-primary/30 bg-primary/5 px-4 py-3 text-sm font-medium text-primary"
            role="status"
            aria-live="polite"
          >
            <Loader2 className="h-4 w-4 shrink-0 animate-spin" aria-hidden />
            <span>
              {t.snapshot.generating}
              <span className="ml-1.5 font-normal text-muted">
                {t.snapshot.generatingBody}
              </span>
            </span>
          </div>
          <SnapshotSkeleton label={t.snapshot.generating} />
        </div>
      );
    }

    // No summary yet (404) — offer to generate, with an optional sample preview.
    return (
      <div className="flex flex-col gap-4">
        <Card className="animate-rise-in border-dashed">
          <CardContent className="flex flex-col items-center gap-4 py-14 text-center">
            <span className="flex h-14 w-14 items-center justify-center rounded-full border border-primary/20 bg-primary/10 text-primary">
              <Sparkles className="h-6 w-6" aria-hidden />
            </span>
            <div className="max-w-md">
              <h2 className="text-lg font-semibold text-foreground">
                {t.snapshot.generateTitle}
              </h2>
              <p className="mt-1.5 text-sm leading-relaxed text-muted text-pretty">
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
              <p role="alert" className="text-sm font-medium text-danger">
                {t.common.error}
              </p>
            )}
            <button
              type="button"
              onClick={() => setShowSample((v) => !v)}
              aria-expanded={showSample}
              className="rounded text-xs font-semibold text-primary underline-offset-4 hover:underline"
            >
              {showSample ? t.snapshot.hideSample : t.snapshot.viewSample}
            </button>
          </CardContent>
        </Card>

        {showSample && (
          <div className="flex animate-expand-down flex-col gap-3">
            <p
              role="note"
              className="rounded-md border border-warning/45 bg-warning-surface px-3.5 py-2.5 text-xs font-semibold text-warning"
            >
              {t.snapshot.sampleBanner}
            </p>
            <PatientSnapshotView data={getMockSnapshot(patientId)} />
          </div>
        )}
      </div>
    );
  }
}
