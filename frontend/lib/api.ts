/**
 * Typed fetch client for the Doc-mate FastAPI backend.
 *
 * Base URL comes from NEXT_PUBLIC_API_URL (default http://localhost:8000).
 * The JWT is stored in localStorage for the demo and attached as a Bearer
 * token on every request. Never put patient data or tokens in URLs.
 */

import type {
  AbhaLookupResult,
  ClinicalItem,
  DocumentDetail,
  DocumentSummary,
  InteractionReport,
  ItemCodes,
  MedicalCode,
  NewPatient,
  Patient,
  PlainSummary,
  Summary,
  SummaryGenerateResponse,
  VoiceTranscription,
} from "./types";

/** Languages Doc-mate can translate the snapshot into. */
export type SummaryLang = "en" | "hi" | "ta" | "te";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

const TOKEN_KEY = "docmate.token";

export type Role = "reception" | "doctor";

export interface LoginResponse {
  access_token: string;
  token_type: string;
  role: Role;
}

export interface User {
  id: string;
  name: string;
  email: string;
  role: Role;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/* ---- token storage (client-only) ---- */

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
}

/* ---- core request helper ---- */

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
  /** Set false to skip the Authorization header (e.g. login). */
  auth?: boolean;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, auth = true, headers, ...rest } = options;

  const finalHeaders = new Headers(headers);
  const isFormData = body instanceof FormData;
  if (body !== undefined && !isFormData) {
    finalHeaders.set("Content-Type", "application/json");
  }
  if (auth) {
    const token = getToken();
    if (token) finalHeaders.set("Authorization", `Bearer ${token}`);
  }
  // Marks writes as already covered by the app-side outbox, so the service
  // worker lets a failure surface here instead of queueing it a second time.
  if (rest.method && rest.method.toUpperCase() !== "GET") {
    finalHeaders.set("X-Docmate-Outbox", "app");
  }

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...rest,
      headers: finalHeaders,
      body: isFormData
        ? (body as FormData)
        : body !== undefined
          ? JSON.stringify(body)
          : undefined,
    });
  } catch {
    throw new ApiError(0, "Network error — is the backend running?");
  }

  if (!res.ok) {
    let message = res.statusText;
    try {
      const data = (await res.json()) as { detail?: string };
      if (data.detail) message = data.detail;
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, message);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/* ---- endpoint methods (match the backend contract) ---- */

export const api = {
  request,

  login(email: string, password: string): Promise<LoginResponse> {
    return request<LoginResponse>("/auth/login", {
      method: "POST",
      auth: false,
      body: { email, password },
    });
  },

  me(): Promise<User> {
    return request<User>("/auth/me");
  },

  get<T>(path: string): Promise<T> {
    return request<T>(path, { method: "GET" });
  },

  post<T>(path: string, body?: unknown): Promise<T> {
    return request<T>(path, { method: "POST", body });
  },

  upload<T>(path: string, form: FormData): Promise<T> {
    return request<T>(path, { method: "POST", body: form });
  },

  /* ---- Patients ---- */

  listPatients(): Promise<Patient[]> {
    return request<Patient[]>("/patients");
  },

  createPatient(body: NewPatient): Promise<Patient> {
    return request<Patient>("/patients", { method: "POST", body });
  },

  getPatient(id: string): Promise<Patient> {
    return request<Patient>(`/patients/${id}`);
  },

  /* ---- Documents ---- */

  listDocuments(patientId: string): Promise<DocumentSummary[]> {
    return request<DocumentSummary[]>(
      `/documents?patient_id=${encodeURIComponent(patientId)}`,
    );
  },

  getDocument(id: string): Promise<DocumentDetail> {
    return request<DocumentDetail>(`/documents/${id}`);
  },

  uploadDocument(input: {
    patientId: string;
    file: File;
    docType?: string;
    encounterId?: string;
  }): Promise<DocumentSummary> {
    const form = new FormData();
    form.set("patient_id", input.patientId);
    form.set("file", input.file);
    if (input.docType) form.set("doc_type", input.docType);
    if (input.encounterId) form.set("encounter_id", input.encounterId);
    return request<DocumentSummary>("/documents", {
      method: "POST",
      body: form,
    });
  },

  verifyDocument(
    id: string,
    itemIds?: ClinicalItem["id"][],
  ): Promise<DocumentDetail> {
    return request<DocumentDetail>(`/documents/${id}/verify`, {
      method: "POST",
      body: itemIds && itemIds.length > 0 ? { item_ids: itemIds } : {},
    });
  },

  /* ---- Summary ---- */

  generateSummary(patientId: string): Promise<SummaryGenerateResponse> {
    return request<SummaryGenerateResponse>(
      `/patients/${patientId}/summary`,
      { method: "POST" },
    );
  },

  getSummary(patientId: string): Promise<Summary> {
    return request<Summary>(`/patients/${patientId}/summary`);
  },

  /** Translated snapshot (same shape as getSummary) in the requested language. */
  getTranslatedSummary(patientId: string, lang: SummaryLang): Promise<Summary> {
    return request<Summary>(
      `/patients/${patientId}/summary/translated?lang=${lang}`,
    );
  },

  /** Patient-friendly plain-language narrative of the snapshot. */
  getPlainSummary(patientId: string, lang: SummaryLang): Promise<PlainSummary> {
    return request<PlainSummary>(
      `/patients/${patientId}/summary/plain?lang=${lang}`,
    );
  },

  /* ---- Contract v2: safety, coding, interoperability ---- */

  /** Drug–drug interactions and allergy conflicts for the patient's meds. */
  getInteractions(patientId: string): Promise<InteractionReport> {
    return request<InteractionReport>(`/patients/${patientId}/interactions`);
  },

  /** ICD-11 / NAMASTE codes mapped to the patient's clinical items. */
  getPatientCodes(patientId: string): Promise<ItemCodes[]> {
    return request<ItemCodes[]>(`/patients/${patientId}/codes`);
  },

  /** Free-text search over a coding system. */
  searchCoding(term: string, system: "icd11" | "namaste"): Promise<MedicalCode[]> {
    return request<MedicalCode[]>(
      `/coding/search?term=${encodeURIComponent(term)}&system=${system}`,
    );
  },

  /** Demo ABHA directory lookup — pre-fills the new-patient form. */
  abhaLookup(abhaId: string): Promise<AbhaLookupResult> {
    return request<AbhaLookupResult>(
      `/abha/lookup?abha_id=${encodeURIComponent(abhaId)}`,
    );
  },

  /** Transcribe a recorded/uploaded audio clip for the intake note. */
  transcribeVoice(audio: Blob, lang?: string): Promise<VoiceTranscription> {
    const form = new FormData();
    const filename =
      audio instanceof File ? audio.name : "recording.webm";
    form.set("audio", audio, filename);
    if (lang) form.set("lang", lang);
    return request<VoiceTranscription>("/voice/transcribe", {
      method: "POST",
      body: form,
    });
  },

  /**
   * Download the patient's FHIR R4 Bundle as a Blob. Uses fetch directly (not
   * the JSON request helper) so the raw body can be saved to a file.
   */
  async fhirBundleBlob(patientId: string): Promise<Blob> {
    const finalHeaders = new Headers();
    const token = getToken();
    if (token) finalHeaders.set("Authorization", `Bearer ${token}`);
    let res: Response;
    try {
      res = await fetch(`${API_URL}/patients/${patientId}/fhir`, {
        method: "GET",
        headers: finalHeaders,
      });
    } catch {
      throw new ApiError(0, "Network error — is the backend running?");
    }
    if (!res.ok) throw new ApiError(res.status, res.statusText);
    return res.blob();
  },
};
