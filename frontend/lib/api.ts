/**
 * Typed fetch client for the Doc-mate FastAPI backend.
 *
 * Base URL comes from NEXT_PUBLIC_API_URL (default http://localhost:8000).
 * The JWT is stored in localStorage for the demo and attached as a Bearer
 * token on every request. Never put patient data or tokens in URLs.
 */

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
};
