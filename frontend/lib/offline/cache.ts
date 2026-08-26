/**
 * Offline read-cache for TanStack Query results.
 *
 * Successful responses for a small allow-list of query keys are mirrored into
 * IndexedDB with the time they were fetched. On startup they are hydrated back
 * into the QueryClient, so a previously-opened patient stays readable during an
 * outage — and the `fetchedAt` stamp lets the UI say exactly how old the copy
 * is instead of passing it off as live (PROJECT.md §4 rule 5).
 */

import type { QueryClient, QueryKey } from "@tanstack/react-query";
import {
  CACHE_TTL_MS,
  idbClear,
  idbDelete,
  idbGetAll,
  idbPut,
  type CacheRecord,
} from "./db";

/**
 * Query-key roots worth keeping for offline reading. Everything else (auth,
 * ad-hoc lookups) is deliberately excluded — an offline cache is PHI at rest,
 * so it holds only what a doctor or the front desk genuinely needs to work
 * through an outage.
 */
const CACHEABLE_ROOTS = new Set([
  "patients",
  "patient",
  "documents",
  "document",
  "summary",
  "interactions",
  "codes",
]);

export function isCacheableKey(key: QueryKey): boolean {
  return Array.isArray(key) && typeof key[0] === "string" && CACHEABLE_ROOTS.has(key[0]);
}

/**
 * Serialise a query key for use as a primary key. Query keys are ids and
 * literals only — no patient names or clinical values ever reach this string
 * (PROJECT.md §4 rule 6).
 */
export function serialiseKey(key: QueryKey): string {
  return JSON.stringify(key);
}

export function deserialiseKey(key: string): QueryKey | null {
  try {
    const parsed: unknown = JSON.parse(key);
    return Array.isArray(parsed) ? (parsed as QueryKey) : null;
  } catch {
    return null;
  }
}

export async function writeCache(key: QueryKey, data: unknown): Promise<void> {
  const record: CacheRecord = {
    key: serialiseKey(key),
    data,
    fetchedAt: Date.now(),
  };
  try {
    await idbPut("cache", record);
  } catch {
    /* Storage full or blocked: the app keeps working, just without an offline copy. */
  }
}

export async function dropCache(key: QueryKey): Promise<void> {
  try {
    await idbDelete("cache", serialiseKey(key));
  } catch {
    /* best effort */
  }
}

export async function clearCache(): Promise<void> {
  try {
    await idbClear("cache");
  } catch {
    /* best effort */
  }
}

/**
 * Drop expired records, then hydrate what survives into the QueryClient.
 * Returns a map of serialised key → fetchedAt so the UI can label each screen
 * with when it last synced.
 */
export async function hydrateCache(
  qc: QueryClient,
): Promise<Record<string, number>> {
  let records: CacheRecord[];
  try {
    records = await idbGetAll<CacheRecord>("cache");
  } catch {
    return {};
  }

  const cutoff = Date.now() - CACHE_TTL_MS;
  const fetchedAt: Record<string, number> = {};

  for (const record of records) {
    if (!record || typeof record.fetchedAt !== "number" || record.fetchedAt < cutoff) {
      // Expired or malformed — remove rather than serve.
      void idbDelete("cache", record?.key).catch(() => {});
      continue;
    }
    const key = deserialiseKey(record.key);
    if (!key || !isCacheableKey(key)) continue;

    // Only seed keys the client has nothing fresher for.
    if (qc.getQueryData(key) === undefined) {
      qc.setQueryData(key, record.data, { updatedAt: record.fetchedAt });
    }
    fetchedAt[record.key] = record.fetchedAt;
  }

  return fetchedAt;
}
