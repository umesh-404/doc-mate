/**
 * TanStack Query hooks for the Doc-mate backend.
 *
 * Central place for cache keys, polling intervals and invalidation so the
 * reception upload/verify flow and the doctor snapshot stay in sync with the
 * server. Polling is used where the backend processes work asynchronously
 * (ingestion status, summary generation).
 */

"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from "@tanstack/react-query";
import { ApiError, api, type SummaryLang } from "./api";
import {
  IN_FLIGHT_STATUSES,
  type ClinicalItem,
  type DocumentDetail,
  type DocumentSummary,
  type InteractionReport,
  type ItemCodes,
  type NewPatient,
  type Patient,
  type PlainSummary,
  type Summary,
} from "./types";

const POLL_MS = 2000;

export const qk = {
  patients: ["patients"] as const,
  patient: (id: string) => ["patient", id] as const,
  documents: (patientId: string) => ["documents", patientId] as const,
  document: (id: string) => ["document", id] as const,
  summary: (patientId: string) => ["summary", patientId] as const,
  summaryTranslated: (patientId: string, lang: string) =>
    ["summary", patientId, "translated", lang] as const,
  summaryPlain: (patientId: string, lang: string) =>
    ["summary", patientId, "plain", lang] as const,
  interactions: (patientId: string) => ["interactions", patientId] as const,
  codes: (patientId: string) => ["codes", patientId] as const,
};

/* ---- Patients ---- */

export function usePatients(): UseQueryResult<Patient[], ApiError> {
  return useQuery({ queryKey: qk.patients, queryFn: api.listPatients });
}

export function usePatient(id: string): UseQueryResult<Patient, ApiError> {
  return useQuery({
    queryKey: qk.patient(id),
    queryFn: () => api.getPatient(id),
    enabled: !!id,
  });
}

export function useCreatePatient() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: NewPatient) => api.createPatient(body),
    onSuccess: (patient) => {
      qc.invalidateQueries({ queryKey: qk.patients });
      qc.setQueryData(qk.patient(patient.id), patient);
    },
  });
}

/* ---- Documents ---- */

/**
 * List a patient's documents, polling every 2s while any document is still
 * in-flight (uploaded/processing) so status badges update live.
 */
export function useDocuments(
  patientId: string,
): UseQueryResult<DocumentSummary[], ApiError> {
  return useQuery({
    queryKey: qk.documents(patientId),
    queryFn: () => api.listDocuments(patientId),
    enabled: !!patientId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return false;
      const anyInFlight = data.some((d) =>
        IN_FLIGHT_STATUSES.includes(d.status),
      );
      return anyInFlight ? POLL_MS : false;
    },
  });
}

/**
 * Detail for a single document (its extracted ClinicalItems). Polls while the
 * document has not finished extracting so the verify list fills in live.
 */
export function useDocument(
  id: string,
  enabled = true,
): UseQueryResult<DocumentDetail, ApiError> {
  return useQuery({
    queryKey: qk.document(id),
    queryFn: () => api.getDocument(id),
    enabled: enabled && !!id,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return POLL_MS;
      return IN_FLIGHT_STATUSES.includes(data.status) ? POLL_MS : false;
    },
  });
}

export function useUploadDocument(patientId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { file: File; docType?: string }) =>
      api.uploadDocument({ patientId, file: input.file, docType: input.docType }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.documents(patientId) });
    },
  });
}

export function useVerifyDocument(patientId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { documentId: string; itemIds?: ClinicalItem["id"][] }) =>
      api.verifyDocument(input.documentId, input.itemIds),
    onSuccess: (detail) => {
      qc.setQueryData(qk.document(detail.id), detail);
      qc.invalidateQueries({ queryKey: qk.documents(patientId) });
    },
  });
}

/* ---- Summary ---- */

/**
 * Fetch the doctor snapshot. A 404 means "no summary yet" — surfaced as
 * `data: null` (not an error) so the UI can offer to generate one. While a
 * generation is in progress, pass `poll` to refetch every 2s until it lands.
 */
export function useSummary(
  patientId: string,
  poll = false,
): UseQueryResult<Summary | null, ApiError> {
  return useQuery({
    queryKey: qk.summary(patientId),
    enabled: !!patientId,
    retry: false,
    queryFn: async () => {
      try {
        return await api.getSummary(patientId);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null;
        throw err;
      }
    },
    refetchInterval: (query) => {
      if (!poll) return false;
      return query.state.data ? false : POLL_MS;
    },
  });
}

export function useGenerateSummary(patientId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.generateSummary(patientId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.summary(patientId) });
    },
  });
}

/**
 * Fetch the snapshot translated into `lang`. Only enabled once a base summary
 * exists and a non-default language is selected; the base query already covers
 * the patient's default language.
 */
export function useTranslatedSummary(
  patientId: string,
  lang: SummaryLang,
  enabled: boolean,
): UseQueryResult<Summary | null, ApiError> {
  return useQuery({
    queryKey: qk.summaryTranslated(patientId, lang),
    enabled: enabled && !!patientId,
    retry: false,
    queryFn: async () => {
      try {
        return await api.getTranslatedSummary(patientId, lang);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null;
        throw err;
      }
    },
  });
}

/** Patient-friendly plain-language narrative, fetched on demand. */
export function usePlainSummary(
  patientId: string,
  lang: SummaryLang,
  enabled: boolean,
): UseQueryResult<PlainSummary | null, ApiError> {
  return useQuery({
    queryKey: qk.summaryPlain(patientId, lang),
    enabled: enabled && !!patientId,
    retry: false,
    queryFn: async () => {
      try {
        return await api.getPlainSummary(patientId, lang);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null;
        throw err;
      }
    },
  });
}

/**
 * Drug-interaction / allergy-conflict report. Surfaced as a verification aid;
 * a missing report (404) is treated as "nothing to surface", not an error.
 */
export function useInteractions(
  patientId: string,
  enabled = true,
): UseQueryResult<InteractionReport | null, ApiError> {
  return useQuery({
    queryKey: qk.interactions(patientId),
    enabled: enabled && !!patientId,
    retry: false,
    queryFn: async () => {
      try {
        return await api.getInteractions(patientId);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null;
        throw err;
      }
    },
  });
}

/** ICD-11 / NAMASTE codes mapped to the patient's items. */
export function usePatientCodes(
  patientId: string,
  enabled = true,
): UseQueryResult<ItemCodes[] | null, ApiError> {
  return useQuery({
    queryKey: qk.codes(patientId),
    enabled: enabled && !!patientId,
    retry: false,
    queryFn: async () => {
      try {
        return await api.getPatientCodes(patientId);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null;
        throw err;
      }
    },
  });
}
