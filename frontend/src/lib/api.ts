import type { BalanceResponse, Dataset, Job, ModelsResponse, User } from "@/types";

const NEXT_PUBLIC_API_URL = process.env.NEXT_PUBLIC_API_URL;

// Validate API URL at module load time — fail loudly if misconfigured in production
const isProd = process.env.NODE_ENV === "production";
if (isProd && !NEXT_PUBLIC_API_URL) {
  throw new Error(
    "NEXT_PUBLIC_API_URL is not configured. " +
    "Set it in .env.production or your deployment environment. " +
    "Example: NEXT_PUBLIC_API_URL=https://api.openreef.com"
  );
}

const API_BASE = NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

type ApiOptions = RequestInit & { headers?: Record<string, string> };

/**
 * Fetch wrapper that:
 * - Sends credentials (cookies) on every request
 * - Attaches X-CSRF-Token header for state-changing requests (POST/PUT/PATCH/DELETE)
 */
async function fetchApi<T>(path: string, opts: ApiOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};

  // Attach CSRF token for state-changing requests
  if (opts.method && ["POST", "PUT", "PATCH", "DELETE"].includes(opts.method.toUpperCase())) {
    const csrfToken = getCsrfCookie();
    if (csrfToken) {
      headers["X-CSRF-Token"] = csrfToken;
    }
  }

  // Merge custom headers
  if (opts.headers) {
    Object.assign(headers, opts.headers);
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...opts,
    credentials: "include",
    headers,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }

  // Handle empty responses (e.g. 200 with no body)
  const text = await res.text();
  if (!text) return {} as T;
  return JSON.parse(text);
}

/** Read the CSRF token from the csrf_token cookie. */
function getCsrfCookie(): string {
  if (typeof document === "undefined") return "";
  const match = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : "";
}

// ── Auth ────────────────────────────────────────────────────────────────

export async function login(email: string, password: string) {
  return fetchApi<{ message: string }>("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export async function register(email: string, password: string) {
  return fetchApi<{ message: string }>("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export async function logout() {
  return fetchApi<{ message: string }>("/api/auth/logout", { method: "POST" });
}

export async function getMe() {
  return fetchApi<User>("/api/auth/me");
}

export async function verifyEmail(token: string) {
  return fetchApi<{ message: string }>("/api/auth/verify-email", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
}

export async function resendVerification(email: string) {
  return fetchApi<{ message: string }>("/api/auth/resend-verification", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
}

// ── Datasets ────────────────────────────────────────────────────────────

export async function listDatasets() {
  return fetchApi<Dataset[]>("/api/datasets");
}

export async function uploadDataset(file: File, name: string) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("name", name);

  // CSRF header required for POST with multipart
  const csrfToken = getCsrfCookie();
  const headers: Record<string, string> = {};
  if (csrfToken) {
    headers["X-CSRF-Token"] = csrfToken;
  }

  const res = await fetch(`${API_BASE}/api/datasets`, {
    method: "POST",
    credentials: "include",
    headers,
    body: formData,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Upload failed: ${res.status}`);
  }

  return res.json();
}

// ── Models ──────────────────────────────────────────────────────────────

export async function listModels() {
  return fetchApi<ModelsResponse>("/api/models");
}

// ── Jobs ────────────────────────────────────────────────────────────────

export async function listJobs() {
  return fetchApi<Job[]>("/api/jobs");
}

export async function getJob(jobId: string) {
  return fetchApi<Job>(`/api/jobs/${jobId}`);
}

export async function createJob(body: {
  dataset_id: string;
  base_model_id: string;
  preset: string;
  adapter: string;
}) {
  return fetchApi<Job>("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function confirmJob(jobId: string) {
  return fetchApi<Job>(`/api/jobs/${jobId}/confirm`, { method: "POST" });
}

export async function cancelJob(jobId: string) {
  return fetchApi<Job>(`/api/jobs/${jobId}/cancel`, { method: "POST" });
}

// ── Payments ────────────────────────────────────────────────────────────

export async function getBalance() {
  return fetchApi<BalanceResponse>("/api/payments/balance");
}

export async function createCheckoutSession(amount_usd: number) {
  return fetchApi<{ checkout_url: string }>("/api/payments/checkout-session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ amount_usd }),
  });
}

export async function devAddCredits(amount: number) {
  return fetchApi<{ balance: number }>("/api/payments/dev-add-credits", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ amount }),
  });
}
