/**
 * Write outbox — the "no lost data" half of offline-first.
 *
 * Reception must be able to keep registering patients and capturing records
 * through an outage (PROJECT.md §1). Every write the app makes goes through
 * here: if it reaches the server, nothing changes; if it cannot, the write is
 * durably queued and replayed later. Nothing is ever silently dropped, and
 * nothing is ever reported as saved until the server has accepted it
 * (PROJECT.md §4 rule 5).
 *
 * IDEMPOTENCY — and its honest limits.
 * Each queued item gets a stable client id at enqueue time and carries it to
 * the server as `X-Client-Request-Id`. The backend does not yet deduplicate on
 * that header, so it is a forward-looking hook, not a guarantee. What this
 * module actually guarantees on its own:
 *   - An item is marked `inflight` in IndexedDB *before* the request goes out,
 *     so a crash mid-flight is visible afterwards.
 *   - A network-layer failure (the request never got a response) returns the
 *     item to `pending`; that is safe to retry.
 *   - An item found `inflight` at startup was interrupted after the request
 *     left. We CANNOT know whether the server applied it, so it is parked as a
 *     conflict for a human to resolve rather than blindly re-sent. That is the
 *     honest behaviour: a duplicate prescription upload is worse than a prompt.
 */

import { API_URL, ApiError, getToken } from "../api";
import type { DocumentSummary, NewPatient, Patient } from "../types";
import {
  idbDelete,
  idbGet,
  idbGetAll,
  idbPut,
  type OutboxRecord,
  type OutboxState,
} from "./db";

/** Give up (and say so) after this many attempts rather than retrying forever. */
export const MAX_ATTEMPTS = 5;

/** Ids minted locally for records the server has not seen yet. */
export const LOCAL_ID_PREFIX = "local-";

export function isLocalId(id: string): boolean {
  return id.startsWith(LOCAL_ID_PREFIX);
}

function newId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

/** 2s, 4s, 8s, 16s, 32s — capped so a long outage does not push retries hours out. */
function backoffMs(attempts: number): number {
  return Math.min(2 ** Math.max(1, attempts) * 1000, 5 * 60 * 1000);
}

/* ------------------------------------------------------------------ */
/* Payload shapes                                                      */
/* ------------------------------------------------------------------ */

export interface CreatePatientPayload {
  body: NewPatient;
  /** The id the UI shows for this patient until the server assigns a real one. */
  localPatientId: string;
}

export interface UploadDocumentPayload {
  /** May be a local id if the patient was also created offline. */
  patientId: string;
  docType?: string;
  filename: string;
  size: number;
  /** The actual bytes. Blobs are structured-cloneable, so IndexedDB holds them. */
  blob: Blob;
}

export interface VerifyDocumentPayload {
  documentId: string;
  itemIds?: string[];
}

export interface RawPayload {
  url: string;
  method: string;
  headers: Record<string, string>;
  body: Blob;
}

/* ------------------------------------------------------------------ */
/* Enqueue                                                             */
/* ------------------------------------------------------------------ */

async function push(
  record: Omit<OutboxRecord, "state" | "attempts" | "createdAt" | "nextAttemptAt" | "lastError">,
): Promise<OutboxRecord> {
  const now = Date.now();
  const full: OutboxRecord = {
    ...record,
    state: "pending",
    attempts: 0,
    createdAt: now,
    nextAttemptAt: now,
    lastError: null,
  };
  await idbPut("outbox", full);
  notify();
  return full;
}

export function enqueueCreatePatient(body: NewPatient): Promise<OutboxRecord> {
  const id = newId();
  const payload: CreatePatientPayload = {
    body,
    localPatientId: `${LOCAL_ID_PREFIX}${id}`,
  };
  return push({ id, kind: "create_patient", label: body.full_name, payload });
}

export function enqueueUploadDocument(
  input: { patientId: string; file: File; docType?: string },
): Promise<OutboxRecord> {
  const payload: UploadDocumentPayload = {
    patientId: input.patientId,
    docType: input.docType,
    filename: input.file.name,
    size: input.file.size,
    blob: input.file,
  };
  return push({
    id: newId(),
    kind: "upload_document",
    label: input.file.name,
    payload,
  });
}

export function enqueueVerifyDocument(
  input: { documentId: string; itemIds?: string[]; label?: string },
): Promise<OutboxRecord> {
  const payload: VerifyDocumentPayload = {
    documentId: input.documentId,
    itemIds: input.itemIds,
  };
  return push({
    id: newId(),
    kind: "verify_document",
    label: input.label,
    payload,
  });
}

/* ------------------------------------------------------------------ */
/* Read / mutate the queue                                             */
/* ------------------------------------------------------------------ */

export async function listOutbox(): Promise<OutboxRecord[]> {
  try {
    const all = await idbGetAll<OutboxRecord>("outbox");
    return all.sort((a, b) => a.createdAt - b.createdAt);
  } catch {
    return [];
  }
}

/** Remove an item the user has decided to abandon. Only ever user-initiated. */
export async function discardOutboxItem(id: string): Promise<void> {
  await idbDelete("outbox", id);
  notify();
}

/** Put a failed/conflicted item back in line for another try, now. */
export async function retryOutboxItem(id: string): Promise<void> {
  const item = await idbGet<OutboxRecord>("outbox", id);
  if (!item) return;
  await idbPut("outbox", {
    ...item,
    state: "pending" as OutboxState,
    attempts: 0,
    nextAttemptAt: Date.now(),
    lastError: null,
    lastStatus: null,
  });
  notify();
}

/**
 * Anything still `inflight` when the app starts was interrupted after its
 * request left the device — it may or may not have been applied. Park it for a
 * human instead of guessing (see the idempotency note at the top of this file).
 */
export async function reconcileInterrupted(): Promise<number> {
  const all = await listOutbox();
  const stuck = all.filter((i) => i.state === "inflight");
  for (const item of stuck) {
    await idbPut("outbox", {
      ...item,
      state: "conflict" as OutboxState,
      lastError: "interrupted",
      lastStatus: null,
    });
  }
  if (stuck.length > 0) notify();
  return stuck.length;
}

/* ------------------------------------------------------------------ */
/* Change notification (lets React re-read without polling IndexedDB)  */
/* ------------------------------------------------------------------ */

type Listener = () => void;
const listeners = new Set<Listener>();

export function subscribeOutbox(fn: Listener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function notify(): void {
  for (const fn of listeners) fn();
}

/* ------------------------------------------------------------------ */
/* Local id → server id mapping                                        */
/* ------------------------------------------------------------------ */

interface IdMapRecord {
  k: string;
  v: Record<string, string>;
}

const ID_MAP_KEY = "localIdMap";

export async function getIdMap(): Promise<Record<string, string>> {
  try {
    const row = await idbGet<IdMapRecord>("meta", ID_MAP_KEY);
    return row?.v ?? {};
  } catch {
    return {};
  }
}

async function recordIdMapping(localId: string, serverId: string): Promise<void> {
  const map = await getIdMap();
  map[localId] = serverId;
  await idbPut("meta", { k: ID_MAP_KEY, v: map });
}

/* ------------------------------------------------------------------ */
/* Replay                                                              */
/* ------------------------------------------------------------------ */

/**
 * HTTP statuses that mean "the server understood and refused". Retrying will
 * not help, so the item becomes a conflict the user can see and resolve — it is
 * never discarded behind their back (PROJECT.md §4 rule 5).
 */
function isConflictStatus(status: number): boolean {
  return status === 400 || status === 403 || status === 404 || status === 409 || status === 422;
}

async function send(
  path: string,
  init: { method: string; body?: BodyInit; json?: unknown },
  clientRequestId: string,
): Promise<Response> {
  const headers = new Headers();
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  // Forward-looking idempotency key; see the module header for its limits.
  headers.set("X-Client-Request-Id", clientRequestId);
  // Tells the service worker this write is already the outbox's problem.
  headers.set("X-Docmate-Outbox", "app");
  let body = init.body;
  if (init.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(init.json);
  }
  return fetch(`${API_URL}${path}`, { method: init.method, headers, body });
}

async function readError(res: Response): Promise<string> {
  try {
    const data = (await res.json()) as { detail?: string };
    if (data?.detail) return data.detail;
  } catch {
    /* fall through */
  }
  return res.statusText || `HTTP ${res.status}`;
}

/** Replay a single item. Throws only for network-layer failures. */
async function replayOne(item: OutboxRecord): Promise<Response> {
  switch (item.kind) {
    case "create_patient": {
      const p = item.payload as CreatePatientPayload;
      return send("/patients", { method: "POST", json: p.body }, item.id);
    }
    case "upload_document": {
      const p = item.payload as UploadDocumentPayload;
      const map = await getIdMap();
      const patientId = isLocalId(p.patientId)
        ? (map[p.patientId] ?? p.patientId)
        : p.patientId;
      if (isLocalId(patientId)) {
        // The patient this belongs to has not synced yet. Not an error — wait.
        throw new ApiError(0, "waiting-for-patient");
      }
      const form = new FormData();
      form.set("patient_id", patientId);
      form.set("file", p.blob, p.filename);
      if (p.docType) form.set("doc_type", p.docType);
      return send("/documents", { method: "POST", body: form }, item.id);
    }
    case "verify_document": {
      const p = item.payload as VerifyDocumentPayload;
      return send(
        `/documents/${p.documentId}/verify`,
        { method: "POST", json: p.itemIds?.length ? { item_ids: p.itemIds } : {} },
        item.id,
      );
    }
    case "raw": {
      const p = item.payload as RawPayload;
      const headers = new Headers(p.headers);
      const token = getToken();
      if (token) headers.set("Authorization", `Bearer ${token}`);
      headers.set("X-Client-Request-Id", item.id);
      headers.set("X-Docmate-Outbox", "app");
      return fetch(p.url, { method: p.method, headers, body: p.body });
    }
  }
}

export interface ReplayResult {
  attempted: number;
  succeeded: number;
  conflicted: number;
  failed: number;
  /** Server ids created during this run, keyed by the local id they replace. */
  resolved: Record<string, string>;
  /** True if the run stopped early because the device is offline. */
  offline: boolean;
}

let replaying = false;

/**
 * Drain the queue. Safe to call concurrently — overlapping calls are collapsed
 * so an item can never be sent twice by two triggers (online event + timer +
 * manual "Sync now").
 */
export async function replayOutbox(): Promise<ReplayResult> {
  const result: ReplayResult = {
    attempted: 0,
    succeeded: 0,
    conflicted: 0,
    failed: 0,
    resolved: {},
    offline: false,
  };
  if (replaying) return result;
  if (typeof navigator !== "undefined" && navigator.onLine === false) {
    result.offline = true;
    return result;
  }
  replaying = true;

  try {
    const now = Date.now();
    const queue = (await listOutbox()).filter(
      (i) => i.state === "pending" && i.nextAttemptAt <= now,
    );

    for (const item of queue) {
      // Mark inflight BEFORE sending, so an interrupted attempt is detectable.
      const attempts = item.attempts + 1;
      await idbPut("outbox", { ...item, state: "inflight" as OutboxState, attempts });
      result.attempted += 1;

      let res: Response;
      try {
        res = await replayOne(item);
      } catch {
        // Never left the device (or is waiting on a dependency): safe to retry.
        const exhausted = attempts >= MAX_ATTEMPTS;
        await idbPut("outbox", {
          ...item,
          attempts,
          state: (exhausted ? "failed" : "pending") as OutboxState,
          nextAttemptAt: Date.now() + backoffMs(attempts),
          lastError: "network",
          lastStatus: 0,
        });
        if (exhausted) result.failed += 1;
        if (typeof navigator !== "undefined" && navigator.onLine === false) {
          result.offline = true;
          break;
        }
        continue;
      }

      if (res.ok) {
        if (item.kind === "create_patient") {
          try {
            const patient = (await res.json()) as Patient;
            const local = (item.payload as CreatePatientPayload).localPatientId;
            await recordIdMapping(local, patient.id);
            result.resolved[local] = patient.id;
          } catch {
            /* body already consumed / unparseable — the write still landed */
          }
        } else if (item.kind === "upload_document") {
          try {
            (await res.json()) as DocumentSummary;
          } catch {
            /* ignore */
          }
        }
        await idbDelete("outbox", item.id);
        result.succeeded += 1;
        continue;
      }

      const message = await readError(res);
      if (isConflictStatus(res.status) || res.status === 401) {
        await idbPut("outbox", {
          ...item,
          attempts,
          state: "conflict" as OutboxState,
          lastError: message,
          lastStatus: res.status,
        });
        result.conflicted += 1;
        continue;
      }

      // 5xx / 429 / anything else: transient, back off and try again.
      const exhausted = attempts >= MAX_ATTEMPTS;
      await idbPut("outbox", {
        ...item,
        attempts,
        state: (exhausted ? "failed" : "pending") as OutboxState,
        nextAttemptAt: Date.now() + backoffMs(attempts),
        lastError: message,
        lastStatus: res.status,
      });
      if (exhausted) result.failed += 1;
    }
  } finally {
    replaying = false;
    notify();
  }

  return result;
}

/** Ask the browser to replay in the background if it supports Background Sync. */
export async function requestBackgroundSync(): Promise<boolean> {
  try {
    if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return false;
    const reg = (await navigator.serviceWorker.ready) as ServiceWorkerRegistration & {
      sync?: { register: (tag: string) => Promise<void> };
    };
    if (!reg.sync) return false;
    await reg.sync.register("docmate-outbox");
    return true;
  } catch {
    // Not supported (Safari, Firefox) or permission-blocked. The `online`
    // listener and the manual "Sync now" action still cover replay.
    return false;
  }
}
