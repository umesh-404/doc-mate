"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  api,
  clearToken,
  getToken,
  setToken,
  type Role,
  type User,
} from "./api";
import { wipeOfflineData } from "./offline/wipe";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

/**
 * Which account last used this browser. Not PHI — just an id — but enough to
 * notice that a different member of staff has signed in on a shared front-desk
 * machine, which must not inherit the previous user's cached records.
 */
const LAST_USER_KEY = "docmate.lastUser";

function readLastUser(): string | null {
  try {
    return window.localStorage.getItem(LAST_USER_KEY);
  } catch {
    return null;
  }
}

function writeLastUser(id: string): void {
  try {
    window.localStorage.setItem(LAST_USER_KEY, id);
  } catch {
    /* blocked storage — the wipe-on-logout path still covers us */
  }
}

type AuthContextValue = {
  user: User | null;
  role: Role | null;
  status: AuthStatus;
  login: (email: string, password: string) => Promise<Role>;
  /** Clears the session AND every byte of local PHI. See lib/offline/wipe.ts. */
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const qc = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  // On mount, if a token exists, try to resolve the current user.
  useEffect(() => {
    const token = getToken();
    if (!token) {
      setStatus("unauthenticated");
      return;
    }
    let active = true;
    api
      .me()
      .then((u) => {
        if (!active) return;
        setUser(u);
        setStatus("authenticated");
      })
      .catch(() => {
        if (!active) return;
        // The stored token is no longer valid. Offline, that is expected (the
        // request simply could not reach /auth/me) and the local copy must
        // survive; online it means the session is genuinely over, so the
        // cached PHI goes with it.
        clearToken();
        setUser(null);
        setStatus("unauthenticated");
        if (navigator.onLine !== false) {
          void wipeOfflineData();
          qc.clear();
        }
      });
    return () => {
      active = false;
    };
  }, [qc]);

  const login = useCallback(
    async (email: string, password: string): Promise<Role> => {
      const res = await api.login(email, password);
      setToken(res.access_token);
      // Resolve the full profile; fall back to a minimal user from the login
      // response if /auth/me is not available yet.
      let resolved: User;
      try {
        resolved = await api.me();
      } catch {
        resolved = { id: email, name: email, email, role: res.role };
      }
      // A different member of staff on a shared terminal must never inherit
      // the previous user's cached records (PROJECT.md §4 rule 6).
      if (readLastUser() && readLastUser() !== resolved.id) {
        await wipeOfflineData();
        qc.clear();
      }
      writeLastUser(resolved.id);
      setUser(resolved);
      setStatus("authenticated");
      return res.role;
    },
    [qc],
  );

  const logout = useCallback(async () => {
    // Session first, so an interrupted wipe can never leave a usable token
    // behind, then every cached record and every queued write.
    clearToken();
    setUser(null);
    setStatus("unauthenticated");
    qc.clear();
    await wipeOfflineData();
    router.push("/");
  }, [qc, router]);

  const value = useMemo<AuthContextValue>(
    () => ({ user, role: user?.role ?? null, status, login, logout }),
    [user, status, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
