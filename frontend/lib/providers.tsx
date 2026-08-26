"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { AuthProvider } from "./auth";
import { I18nProvider } from "./i18n";
import { OfflineProvider } from "./offline/provider";
import { ServiceWorkerRegistrar } from "./offline/register-sw";
import { ThemeProvider } from "./theme";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 1,
            refetchOnWindowFocus: false,
            // Offline-first: a paused query keeps serving the copy hydrated
            // from IndexedDB instead of erroring, and resumes on reconnect.
            // (This is TanStack's default; stated explicitly because the whole
            // offline read path depends on it.)
            networkMode: "online",
            // Refetch as soon as the link returns so a cached snapshot is
            // never left stale once it can be refreshed.
            refetchOnReconnect: true,
          },
          mutations: {
            // Mutations must NOT pause offline — they have to reach the outbox
            // so the user gets a truthful "queued" state (PROJECT.md §4.5).
            networkMode: "always",
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <I18nProvider>
          <OfflineProvider>
            <ServiceWorkerRegistrar />
            <AuthProvider>{children}</AuthProvider>
          </OfflineProvider>
        </I18nProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
