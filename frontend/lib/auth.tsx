"use client";

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

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

type AuthContextValue = {
  user: User | null;
  role: Role | null;
  status: AuthStatus;
  login: (email: string, password: string) => Promise<Role>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
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
        clearToken();
        setUser(null);
        setStatus("unauthenticated");
      });
    return () => {
      active = false;
    };
  }, []);

  const login = useCallback(async (email: string, password: string): Promise<Role> => {
    const res = await api.login(email, password);
    setToken(res.access_token);
    // Resolve the full profile; fall back to a minimal user from the login
    // response if /auth/me is not available yet.
    try {
      const u = await api.me();
      setUser(u);
    } catch {
      setUser({ id: email, name: email, email, role: res.role });
    }
    setStatus("authenticated");
    return res.role;
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
    setStatus("unauthenticated");
    router.push("/");
  }, [router]);

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
