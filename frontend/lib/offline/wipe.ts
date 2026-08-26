/**
 * Sign-out wipe (PROJECT.md §4 rule 6).
 *
 * A front-desk terminal is shared. Everything Doc-mate stored locally — cached
 * patient records, queued uploads, the document blobs inside them, and every
 * Cache Storage entry — is deleted when the user signs out. This is deliberately
 * unconditional and total: there is no "keep my drafts" path for PHI.
 *
 * Returns a report so the caller can tell the user plainly if part of the wipe
 * did not complete (e.g. another tab is holding the database open).
 */

import { deleteDatabase, idbAvailable, idbGetAll, resetDBHandle } from "./db";

export interface WipeReport {
  cachesDeleted: number;
  databaseDeleted: boolean;
  /** Queued writes that were destroyed along with everything else. */
  pendingDiscarded: number;
  errors: string[];
}

/** Ask the service worker to drop its caches too, and wait for confirmation. */
function wipeServiceWorkerCaches(): Promise<void> {
  return new Promise((resolve) => {
    if (typeof navigator === "undefined" || !navigator.serviceWorker?.controller) {
      resolve();
      return;
    }
    const channel = new MessageChannel();
    const timer = setTimeout(resolve, 1500); // never block sign-out on the SW
    channel.port1.onmessage = () => {
      clearTimeout(timer);
      resolve();
    };
    try {
      navigator.serviceWorker.controller.postMessage({ type: "WIPE_CACHES" }, [
        channel.port2,
      ]);
    } catch {
      clearTimeout(timer);
      resolve();
    }
  });
}

export async function wipeOfflineData(): Promise<WipeReport> {
  const report: WipeReport = {
    cachesDeleted: 0,
    databaseDeleted: false,
    pendingDiscarded: 0,
    errors: [],
  };

  // Count what is about to be destroyed so the UI can warn honestly.
  if (idbAvailable()) {
    try {
      const queued = await idbGetAll<unknown>("outbox");
      report.pendingDiscarded = queued.length;
    } catch {
      /* nothing queued, or the store is unreadable — not worth failing over */
    }
  }

  // 1. Cache Storage — cached API responses and route HTML both live here.
  if (typeof caches !== "undefined") {
    try {
      const keys = await caches.keys();
      const results = await Promise.all(keys.map((k) => caches.delete(k)));
      report.cachesDeleted = results.filter(Boolean).length;
    } catch (err) {
      report.errors.push(`caches: ${String(err)}`);
    }
  }
  await wipeServiceWorkerCaches();

  // 2. IndexedDB — cached records, the outbox, and the file blobs it holds.
  try {
    await deleteDatabase();
    report.databaseDeleted = await verifyDatabaseGone();
    if (!report.databaseDeleted) {
      report.errors.push("indexeddb: delete blocked by another open tab");
    }
  } catch (err) {
    report.errors.push(`indexeddb: ${String(err)}`);
  }

  resetDBHandle();
  return report;
}

/**
 * Confirm the database is actually gone rather than assuming it.
 * `indexedDB.databases()` is unavailable in Firefox, where we fall back to
 * opening the database and checking that it comes back empty (a fresh open
 * fires `upgradeneeded` and creates version 1 with no rows).
 */
async function verifyDatabaseGone(): Promise<boolean> {
  if (!idbAvailable()) return true;
  const withDatabases = indexedDB as IDBFactory & {
    databases?: () => Promise<{ name?: string }[]>;
  };
  if (typeof withDatabases.databases === "function") {
    try {
      const list = await withDatabases.databases();
      return !list.some((d) => d.name === "docmate-offline");
    } catch {
      /* fall through to the probe below */
    }
  }
  try {
    const rows = await idbGetAll<unknown>("cache");
    const queued = await idbGetAll<unknown>("outbox");
    return rows.length === 0 && queued.length === 0;
  } catch {
    return true; // cannot even open it — nothing readable remains
  }
}
