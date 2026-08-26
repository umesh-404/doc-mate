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
  /** Free-text reason-for-visit / intake note (may be voice-transcribed). */
  note?: string;
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
  /** Contract v2: whether this line is supported by a retrieved source. */
  grounded?: boolean | null;
  /** Contract v2: short note explaining an ungrounded/uncertain line. */
  grounding_note?: string | null;
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

/** Contract v2: overall grounding score for the generated snapshot. */
export interface Grounding {
  score: number; // 0..1
  method: string;
  unsupported_count: number;
}

export type AlertLevel = "critical" | "warning" | "info";
export type AlertKind =
  | "allergy"
  | "interaction"
  | "abnormal_lab"
  | "missing_data";

/** Contract v2: a surfaced alert the doctor should verify (never a directive). */
export interface SummaryAlert {
  level: AlertLevel;
  kind: AlertKind;
  text: string;
  citations: SummaryCitation[];
}

export interface Summary {
  id: string;
  patient_id: string;
  language: string;
  generated_at: string;
  sections: SummarySection[];
  /** Contract v2 additions (optional so v1 responses still type-check). */
  grounding?: Grounding | null;
  alerts?: SummaryAlert[] | null;
}

/* ---- Drug interactions (contract v2) ---- */

export type InteractionSeverity =
  | "contraindicated"
  | "major"
  | "moderate"
  | "minor";

export interface DrugInteraction {
  drug_a: string;
  drug_b: string;
  severity: InteractionSeverity;
  description: string;
  source: string;
}

export interface AllergyConflict {
  medication: string;
  allergen: string;
  note: string;
  source: string;
}

export interface InteractionReport {
  checked_at: string;
  medications: { name: string; rxcui?: string | null }[];
  interactions: DrugInteraction[];
  allergy_conflicts: AllergyConflict[];
}

/* ---- Coding (ICD-11 / NAMASTE) (contract v2) ---- */

export interface MedicalCode {
  system: string;
  code: string;
  display: string;
}

export interface ItemCodes {
  item_label: string;
  kind: string;
  codes: MedicalCode[];
}

/* ---- ABHA lookup (contract v2, demo/mock) ---- */

export interface AbhaLookupResult {
  abha_id: string;
  name: string;
  gender: string;
  year_of_birth: number;
  verified: boolean;
  source: string;
}

/* ---- Plain-language summary (contract v2) ---- */

export interface PlainSummary {
  language: string;
  text: string;
}

/* ---- Voice transcription (contract v2) ---- */

export interface VoiceTranscription {
  text: string;
  lang: string;
  confidence: number;
  stub: boolean;
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
