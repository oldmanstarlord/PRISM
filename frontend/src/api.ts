import { supabase } from "./supabase";

export const apiBase = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

async function sessionHeaders(headers?: HeadersInit): Promise<Headers> {
  const result = new Headers(headers);
  if (supabase) {
    const { data } = await supabase.auth.getSession();
    if (data.session?.access_token) {
      result.set("Authorization", `Bearer ${data.session.access_token}`);
    }
  }
  return result;
}

export async function fetchJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    signal,
    headers: await sessionHeaders(),
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `API returned ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function postJson<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const headers = await sessionHeaders({ "Content-Type": "application/json" });
  const response = await fetch(`${apiBase}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    throw new Error(errorMessage(payload, response.status));
  }
  return (await response.json()) as T;
}

function errorMessage(payload: unknown, status: number) {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && "message" in detail) {
      return String((detail as { message: unknown }).message);
    }
  }
  return `API returned ${status}`;
}

export async function fetchAuthenticatedJson<T>(
  path: string,
  token: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (init.body) headers.set("Content-Type", "application/json");
  const response = await fetch(`${apiBase}${path}`, { ...init, headers });
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    throw new Error(errorMessage(payload, response.status));
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function fetchPortfolioDecisionAnalysis(
  holdings: Array<{
    symbol: string;
    company_name?: string | null;
    sector?: string | null;
    quantity: number;
    buy_price?: number;
    weight?: number;
  }>,
  signal?: AbortSignal,
) {
  return postJson<import("./types").PortfolioDecisionResponse>(
    "/portfolio/analyze",
    { holdings },
    signal,
  );
}
