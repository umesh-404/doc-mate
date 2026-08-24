/**
 * Types for SHARED API CONTRACT v1.
 *
 * These mirror the backend response shapes exactly (snake_case fields as the
 * API returns them). The backend is being built against this same contract, so
 * keep these in lockstep with docs/PROJECT.md §9 and the agreed endpoints.
 */

import type { Role } from "./api";

export type { Role };

/* ---- Patients ---- */

export type Sex = "M" | "F" | "O";

export interface Patient {
  id: string;
  full_name: string;
  age?: number | null;
  sex?: Sex | null;
  abha_id?: string | null;
  preferred_language: string;
  phone?: string | null;
  created_at: string;
}

export interface NewPatient {
  full_name: string;
  age?: number;
  sex?: Sex;
  abha_id?: string;
  preferred_language?: string;
  phone?: string;
}

/* ---- Documents ---- */

export type DocumentStatus =
  | "uploaded"
  | "processing"
  | "extracted"
  | "verified"
  | "failed";

/** Doc statuses that are still moving through the ingestion pipeline. */
export const IN_FLIGHT_STATUSES: DocumentStatus[] = ["uploaded", "processing"];

export interface DocumentSummary {
  id: string;
  patient_id: string;
  doc_type: string;
  filename: string;
  status: DocumentStatus;
  confidence?: number | null;
  created_at: string;
}

export type ClinicalKind =
  | "observation"
  | "medication"
  | "allergy"
  | "condition"
  | "procedure";

export interface ClinicalItem {
  id: string;
  kind: ClinicalKind;
  label: string;
  value?: string | null;
  unit?: string | null;
  date?: string | null;
  confidence: number;
  verified: boolean;
  source_document_id: string;
}

export interface DocumentDetail extends DocumentSummary {
  extracted_text?: string | null;
  error?: string | null;
  items: ClinicalItem[];
}

/* ---- Summary (doctor snapshot) ---- */

export type SummarySeverity = "high" | "med" | "low";
export type SummaryTrend = "up" | "down" | "flat";

export interface SummaryCitation {
  document_id: string;
  label: string;
}

export interface SummaryItem {
  text: string;
  severity?: SummarySeverity | null;
  trend?: SummaryTrend | null;
  confidence?: number | null;
  verified?: boolean | null;
  citations: SummaryCitation[];
}

export type SectionKey =
  | "complaint"
  | "problems"
  | "allergies"
  | "medications"
  | "labs"
  | "encounters"
  | "flags";

export interface SummarySection {
  key: SectionKey;
  title: string;
  items: SummaryItem[];
}

export interface Summary {
  id: string;
  patient_id: string;
  language: string;
  generated_at: string;
  sections: SummarySection[];
}

export interface SummaryGenerateResponse {
  status: "generating" | "ready";
  summary_id?: string;
}

/* ---- Shared helpers ---- */

/**
 * Confidence below this is surfaced as "needs verification" (⚠). OCR on medical
 * handwriting tops out ~82–95% (PROJECT.md §4.4), so anything less than a strong
 * read is flagged for a human to confirm.
 */
export const LOW_CONFIDENCE = 0.85;

export const CLINICAL_KIND_LABEL: Record<ClinicalKind, string> = {
  observation: "Observation",
  medication: "Medication",
  allergy: "Allergy",
  condition: "Condition",
  procedure: "Procedure",
};

/** Selectable document types for the upload step. */
export const DOC_TYPES: { value: string; labelKey: string }[] = [
  { value: "prescription", labelKey: "prescription" },
  { value: "lab_report", labelKey: "labReport" },
  { value: "discharge_summary", labelKey: "dischargeSummary" },
  { value: "scan", labelKey: "scan" },
  { value: "note", labelKey: "note" },
  { value: "other", labelKey: "other" },
];
