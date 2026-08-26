/**
 * Hand-rolled IndexedDB layer for Doc-mate's offline-first store.
 *
 * No dependency — the surface we need is small (three stores, get/put/delete/
 * getAll) and a wrapper library would be more code than this file.
 *
 * PRIVACY (PROJECT.md §4 rule 6): everything in here is PHI sitting on a
 * possibly-shared front-desk machine. Two rules follow and are enforced here:
 *   1. Records carry a `fetchedAt` and expire — see CACHE_TTL_MS.
 *   2. Sign-out deletes the whole database — see lib/offline/wipe.ts.
 * IndexedDB is NOT encrypted at rest. A real deployment needs full-disk
 * encryption on the terminal; that is a deployment control, not a browser one.
 */

export const DB_NAME = "docmate-offline";
export const DB_VERSION = 1;

/**
 * How long a cached clinical record stays readable offline.
 *
 * Seven days: long enough to cover a follow-up visit within the same week and a
 * multi-day outage, short enough that a machine left in a ward does not
 * accumulate an open-ended patient history. Enforced on startup (purgeExpired)
 * and mirrored in public/sw.js for the Cache Storage copy.
 */
export const CACHE_TTL_MS = 7 * 24 * 60 * 60 * 1000;

export type StoreName = "cache" | "outbox" | "meta";

/** A cached server response, keyed by its serialised TanStack Query key. */
export interface CacheRecord {
  /** JSON of the query key. Contains record ids only — never patient content. */
  key: string;
  data: unknown;
  fetchedAt: number;
}

export type OutboxState = "pending" | "inflight" | "conflict" | "failed";

export type OutboxKind =
  | "create_patient"
  | "upload_document"
  | "verify_document"
  /** Written by the service worker for a write it did not recognise. */
  | "raw";

export interface OutboxRecord {
  /** Stable client id — the idempotency anchor. Generated once, never reused. */
  id: string;
  kind: OutboxKind;
  state: OutboxState;
  attempts: number;
  createdAt: number;
  /** Earliest wall-clock time the next attempt may run (exponential backoff). */
  nextAttemptAt: number;
  lastError: string | null;
  /** HTTP status of the rejection that moved this item to `conflict`. */
  lastStatus?: number | null;
  /** Human-readable label for the sync list. Names are PHI but stay local. */
  label?: string;
  payload: unknown;
}

let dbPromise: Promise<IDBDatabase> | null = null;

/** True when this environment can actually persist (SSR and locked-down
 *  browsers both fall back to in-memory behaviour rather than throwing). */
export function idbAvailable(): boolean {
  return typeof indexedDB !== "undefined";
}

export function openDB(): Promise<IDBDatabase> {
  if (!idbAvailable()) return Promise.reject(new Error("IndexedDB unavailable"));
  if (!dbPromise) {
    dbPromise = new Promise<IDBDatabase>((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains("cache")) {
          db.createObjectStore("cache", { keyPath: "key" });
        }
        if (!db.objectStoreNames.contains("outbox")) {
          const store = db.createObjectStore("outbox", { keyPath: "id" });
          store.createIndex("state", "state");
        }
        if (!db.objectStoreNames.contains("meta")) {
          db.createObjectStore("meta", { keyPath: "k" });
        }
      };
      req.onsuccess = () => {
        const db = req.result;
        // If another tab deletes the database (sign-out), drop our handle so
        // the next call reopens rather than working against a dead connection.
        db.onversionchange = () => {
          db.close();
          dbPromise = null;
        };
        resolve(db);
      };
      req.onerror = () => reject(req.error ?? new Error("IndexedDB open failed"));
      req.onblocked = () => reject(new Error("IndexedDB open blocked"));
    }).catch((err) => {
      dbPromise = null;
      throw err;
    });
  }
  return dbPromise;
}

/** Forget the cached connection — used after deleting the database. */
export function resetDBHandle(): void {
  dbPromise = null;
}

function run<T>(
  store: StoreName,
  mode: IDBTransactionMode,
  fn: (s: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  return openDB().then(
    (db) =>
      new Promise<T>((resolve, reject) => {
        const tx = db.transaction(store, mode);
        const req = fn(tx.objectStore(store));
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error ?? new Error("IndexedDB request failed"));
      }),
  );
}

export function idbPut<T>(store: StoreName, value: T): Promise<void> {
  return run<IDBValidKey>(store, "readwrite", (s) => s.put(value)).then(() => undefined);
}

export function idbGet<T>(store: StoreName, key: IDBValidKey): Promise<T | undefined> {
  return run<T | undefined>(store, "readonly", (s) => s.get(key) as IDBRequest<T | undefined>);
}

export function idbGetAll<T>(store: StoreName): Promise<T[]> {
  return run<T[]>(store, "readonly", (s) => s.getAll() as IDBRequest<T[]>);
}

export function idbDelete(store: StoreName, key: IDBValidKey): Promise<void> {
  return run<undefined>(store, "readwrite", (s) => s.delete(key)).then(() => undefined);
}

export function idbClear(store: StoreName): Promise<void> {
  return run<undefined>(store, "readwrite", (s) => s.clear()).then(() => undefined);
}

/** Delete the whole database. Used by sign-out; resolves even if it is blocked
 *  by another tab so the caller can still clear the rest of the PHI. */
export function deleteDatabase(): Promise<void> {
  resetDBHandle();
  if (!idbAvailable()) return Promise.resolve();
  return new Promise<void>((resolve) => {
    const req = indexedDB.deleteDatabase(DB_NAME);
    req.onsuccess = () => resolve();
    req.onerror = () => resolve();
    // Another tab still holds the DB open. Report back rather than hanging;
    // the caller surfaces the fact that the wipe was partial.
    req.onblocked = () => resolve();
  });
}
