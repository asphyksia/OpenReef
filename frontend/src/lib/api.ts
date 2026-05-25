import type { User, Dataset, Job, ModelsResponse, BalanceResponse } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

function getHeaders(token?: string): HeadersInit {
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

async function fetchApi<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") || "" : "";
  const res = await fetch(`${API_BASE}${path}`, {
    ...opts,
    headers: { ...getHeaders(token), ...opts.headers },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const msg = body?.detail || body?.message || res.statusText;
    throw new Error(msg);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

// Auth
export async function login(email: string, password: string) {
  const data = await fetchApi<{ access_token: string }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  localStorage.setItem("token", data.access_token);
  return data;
}

export async function register(email: string, password: string) {
  const data = await fetchApi<{ access_token: string }>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  localStorage.setItem("token", data.access_token);
  return data;
}

export async function getMe(): Promise<User> {
  return fetchApi<User>("/api/auth/me");
}

// Datasets
export async function listDatasets(): Promise<Dataset[]> {
  return fetchApi<Dataset[]>("/api/datasets");
}

export async function uploadDataset(file: File, name: string): Promise<Dataset> {
  const token = localStorage.getItem("token") || "";
  const formData = new FormData();
  formData.append("file", file);
  formData.append("name", name);

  const res = await fetch(`${API_BASE}/api/datasets`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ? JSON.stringify(body.detail) : res.statusText);
  }
  return res.json();
}

// Jobs
export async function listJobs(): Promise<Job[]> {
  return fetchApi<Job[]>("/api/jobs");
}

export async function getJob(id: string): Promise<Job> {
  return fetchApi<Job>(`/api/jobs/${id}`);
}

export async function createJob(params: {
  dataset_id: string;
  base_model_id: string;
  preset: string;
  adapter: string;
}): Promise<Job> {
  return fetchApi<Job>("/api/jobs", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function confirmJob(id: string): Promise<Job> {
  return fetchApi<Job>(`/api/jobs/${id}/confirm`, { method: "POST" });
}

export async function cancelJob(id: string): Promise<Job> {
  return fetchApi<Job>(`/api/jobs/${id}/cancel`, { method: "POST" });
}

// Models
export async function getModels(): Promise<ModelsResponse> {
  return fetchApi<ModelsResponse>("/api/models");
}

// Payments
export async function getBalance(): Promise<BalanceResponse> {
  return fetchApi<BalanceResponse>("/api/payments/balance");
}

export async function createCheckoutSession(amountUsd: number): Promise<{ checkout_url: string }> {
  return fetchApi<{ checkout_url: string }>("/api/payments/checkout-session", {
    method: "POST",
    body: JSON.stringify({ amount_usd: amountUsd }),
  });
}

export async function devAddCredits(amount: number): Promise<{ balance: number }> {
  return fetchApi<{ balance: number }>(`/api/payments/dev-add-credits?amount=${amount}`, {
    method: "POST",
  });
}
