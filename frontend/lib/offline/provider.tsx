"use client";

/**
 * Offline runtime for the app: connectivity state, the read-cache bridge into
 * TanStack Query, and the outbox's replay triggers.
 *
 * Mounted inside QueryClientProvider (it needs the client) and outside
 * AuthProvider (sign-out reaches the wipe helper directly, not through here).
 */

import { useQueryClient, type QueryKey } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { hydrateCache, isCacheableKey, serialiseKey, writeCache } from "./cache";
import type { OutboxRecord } from "./db";
import {
  discardOutboxItem,
  listOutbox,
  reconcileInterrupted,
  replayOutbox,
  requestBackgroundSync,
  retryOutboxItem,
  subscribeOutbox,
} from "./outbox";

/** While anything is queued, retry on a slow timer as well as on `online`. */
const RETRY_TICK_MS = 20_000;

type OfflineContextValue = {
  /** Live connectivity, from the browser. Optimistic by nature: `true` only
   *  means the device has a network, not that the API is reachable. */
  online: boolean;
  /** True once the IndexedDB read-cache has been merged into the QueryClient. */
  hydrated: boolean;
  /** When this query key last came back from the server, or null if never. */
  lastSyncedAt: (key: QueryKey) => number | null;
  outbox: OutboxRecord[];
  pendingCount: number;
  attentionCount: number;
  syncing: boolean;
  syncNow: () => Promise<void>;
  retryItem: (id: string) => Promise<void>;
  discardItem: (id: string) => Promise<void>;
};

const OfflineContext = createContext<OfflineContextValue | null>(null);

function readOnline(): boolean {
  if (typeof navigator === "undefined") return true;
  return navigator.onLine !== false;
}

export function OfflineProvider({ children }: { children: React.ReactNode }) {
  const qc = useQueryClient();
  // Server render and first paint assume online; the mount effect corrects it.
  const [online, setOnline] = useState(true);
  const [hydrated, setHydrated] = useState(false);
  const [fetchedAt, setFetchedAt] = useState<Record<string, number>>({});
  const [outbox, setOutbox] = useState<OutboxRecord[]>([]);
  const [syncing, setSyncing] = useState(false);
  const syncingRef = useRef(false);

  const refreshOutbox = useCallback(() => {
    void listOutbox().then(setOutbox);
  }, []);

  const runReplay = useCallback(async () => {
    if (syncingRef.current) return;
    syncingRef.current = true;
    setSyncing(true);
    try {
      const result = await replayOutbox();
      if (result.succeeded > 0 || Object.keys(result.resolved).length > 0) {
        // Anything the server now owns must be re-read rather than trusted from
        // local state — the backend assigns ids, statuses and timestamps.
        await qc.invalidateQueries();
      }
    } finally {
      syncingRef.current = false;
      setSyncing(false);
      refreshOutbox();
    }
  }, [qc, refreshOutbox]);

  /* ---- startup: purge, hydrate, reconcile ---- */
  useEffect(() => {
    let active = true;
    setOnline(readOnline());

    void (async () => {
      // hydrateCache drops anything past the TTL before seeding the client.
      const seeded = await hydrateCache(qc);
      if (!active) return;
      setFetchedAt((prev) => ({ ...seeded, ...prev }));
      setHydrated(true);
      await reconcileInterrupted();
      if (!active) return;
      refreshOutbox();
      if (readOnline()) void runReplay();
    })();

    return () => {
      active = false;
    };
  }, [qc, refreshOutbox, runReplay]);

  /* ---- mirror successful queries into IndexedDB ---- */
  useEffect(() => {
    const unsubscribe = qc.getQueryCache().subscribe((event) => {
      if (event.type !== "updated") return;
      const action = event.action as { type: string; data?: unknown };
      if (action.type !== "success") return;
      const key = event.query.queryKey;
      if (!isCacheableKey(key)) return;
      if (action.data === undefined) return;
      const serialised = serialiseKey(key);
      const now = Date.now();
      setFetchedAt((prev) => ({ ...prev, [serialised]: now }));
      void writeCache(key, action.data);
    });
    return unsubscribe;
  }, [qc]);

  /* ---- outbox change notifications ---- */
  useEffect(() => subscribeOutbox(refreshOutbox), [refreshOutbox]);

  /* ---- connectivity transitions ---- */
  useEffect(() => {
    const goOnline = () => {
      setOnline(true);
      void requestBackgroundSync();
      void runReplay();
      // Paused queries resume on their own, but a nudge makes the snapshot
      // refresh the moment the link returns rather than on next focus.
      void qc.invalidateQueries();
    };
    const goOffline = () => setOnline(false);
    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    return () => {
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline", goOffline);
    };
  }, [qc, runReplay]);

  /* ---- the service worker's Background Sync wakes us to do the replay ---- */
  useEffect(() => {
    if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return;
    const onMessage = (event: MessageEvent) => {
      if ((event.data as { type?: string } | null)?.type === "REPLAY_OUTBOX") {
        void runReplay();
      }
    };
    navigator.serviceWorker.addEventListener("message", onMessage);
    return () => navigator.serviceWorker.removeEventListener("message", onMessage);
  }, [runReplay]);

  /* ---- slow retry tick while work is queued ---- */
  const hasPending = outbox.some((i) => i.state === "pending" || i.state === "inflight");
  useEffect(() => {
    if (!hasPending || !online) return;
    const timer = window.setInterval(() => void runReplay(), RETRY_TICK_MS);
    return () => window.clearInterval(timer);
  }, [hasPending, online, runReplay]);

  const lastSyncedAt = useCallback(
    (key: QueryKey) => fetchedAt[serialiseKey(key)] ?? null,
    [fetchedAt],
  );

  const retryItem = useCallback(
    async (id: string) => {
      await retryOutboxItem(id);
      await runReplay();
    },
    [runReplay],
  );

  const discardItem = useCallback(async (id: string) => {
    await discardOutboxItem(id);
  }, []);

  const pendingCount = outbox.filter(
    (i) => i.state === "pending" || i.state === "inflight",
  ).length;
  const attentionCount = outbox.filter(
    (i) => i.state === "failed" || i.state === "conflict",
  ).length;

  const value = useMemo<OfflineContextValue>(
    () => ({
      online,
      hydrated,
      lastSyncedAt,
      outbox,
      pendingCount,
      attentionCount,
      syncing,
      syncNow: runReplay,
      retryItem,
      discardItem,
    }),
    [
      online,
      hydrated,
      lastSyncedAt,
      outbox,
      pendingCount,
      attentionCount,
      syncing,
      runReplay,
      retryItem,
      discardItem,
    ],
  );

  return <OfflineContext.Provider value={value}>{children}</OfflineContext.Provider>;
}

export function useOffline(): OfflineContextValue {
  const ctx = useContext(OfflineContext);
  if (!ctx) {
    throw new Error("useOffline must be used within an OfflineProvider");
  }
  return ctx;
}

/**
 * Queued writes for one patient, so a screen can show what has not reached the
 * server yet. Returned straight from the outbox — never merged into query data,
 * because query data means "what the server has".
 */
export function usePendingFor(patientId: string | null) {
  const { outbox } = useOffline();
  return useMemo(() => {
    const documents = outbox.filter(
      (i) =>
        i.kind === "upload_document" &&
        (!patientId ||
          (i.payload as { patientId?: string }).patientId === patientId),
    );
    const patients = outbox.filter((i) => i.kind === "create_patient");
    const verifications = outbox.filter((i) => i.kind === "verify_document");
    return { documents, patients, verifications };
  }, [outbox, patientId]);
}
