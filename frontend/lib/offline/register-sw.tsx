"use client";

/**
 * Service worker registration.
 *
 * DEV: deliberately NOT registered. A worker that caches the shell fights
 * Next.js hot reload — you edit a file and get yesterday's HTML back. Any
 * worker left over from a production build on the same origin (localhost is
 * commonly both) is actively unregistered so `npm run dev` is always clean.
 * The IndexedDB read-cache and the outbox still run in dev, so offline
 * behaviour remains testable without the worker.
 *
 * PROD: registered after load so it never competes with first paint.
 */

import { useEffect } from "react";
import { API_URL } from "../api";

function apiOrigin(): string | null {
  try {
    return new URL(API_URL, window.location.href).origin;
  } catch {
    return null;
  }
}

export function ServiceWorkerRegistrar() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;

    if (process.env.NODE_ENV !== "production") {
      void navigator.serviceWorker.getRegistrations().then((regs) => {
        for (const reg of regs) void reg.unregister();
      });
      return;
    }

    const origin = apiOrigin();

    const register = () => {
      void navigator.serviceWorker
        .register("/sw.js", { scope: "/" })
        .then(() => navigator.serviceWorker.ready)
        .then(() => {
          // The worker file is static and cannot read NEXT_PUBLIC_API_URL, so
          // the API origin is handed over at runtime and persisted by the SW.
          if (origin && navigator.serviceWorker.controller) {
            navigator.serviceWorker.controller.postMessage({
              type: "SET_API_ORIGIN",
              origin,
            });
          }
        })
        .catch(() => {
          /* Registration can fail on an insecure origin or a locked-down
             browser. The app keeps working; it just is not installable. */
        });
    };

    if (document.readyState === "complete") register();
    else window.addEventListener("load", register, { once: true });

    // A *replacement* worker taking over means new shell HTML, so reload to keep
    // the page consistent with the assets it is about to be served. The very
    // first registration also fires this event; reloading then would bounce
    // every new visitor, so it is ignored unless a controller was already there.
    const hadController = !!navigator.serviceWorker.controller;
    let refreshing = false;
    const onControllerChange = () => {
      if (!hadController || refreshing) return;
      refreshing = true;
      window.location.reload();
    };
    navigator.serviceWorker.addEventListener("controllerchange", onControllerChange);
    return () => {
      window.removeEventListener("load", register);
      navigator.serviceWorker.removeEventListener("controllerchange", onControllerChange);
    };
  }, []);

  return null;
}
