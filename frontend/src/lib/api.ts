const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

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
  return fetchApi("/api/auth/me");
}

// ── Datasets ────────────────────────────────────────────────────────────

export async function listDatasets() {
  return fetchApi("/api/datasets");
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
  return fetchApi("/api/models");
}

// ── Jobs ────────────────────────────────────────────────────────────────

export async function listJobs() {
  return fetchApi("/api/jobs");
}

export async function getJob(jobId: string) {
  return fetchApi(`/api/jobs/${jobId}`);
}

export async function createJob(body: {
  dataset_id: string;
  base_model_id: string;
  preset: string;
  adapter: string;
}) {
  return fetchApi("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function confirmJob(jobId: string) {
  return fetchApi(`/api/jobs/${jobId}/confirm`, { method: "POST" });
}

export async function cancelJob(jobId: string) {
  return fetchApi(`/api/jobs/${jobId}/cancel`, { method: "POST" });
}

// ── Payments ────────────────────────────────────────────────────────────

export async function getBalance() {
  return fetchApi("/api/payments/balance");
}

export async function createCheckoutSession(amount_usd: number) {
  return fetchApi("/api/payments/checkout-session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ amount_usd }),
  });
}

export async function devAddCredits(amount: number) {
  return fetchApi("/api/payments/dev-add-credits", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ amount }),
  });
}
