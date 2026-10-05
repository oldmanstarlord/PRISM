import {
  useQuery,
  type UseQueryOptions,
  type UseQueryResult,
} from "@tanstack/react-query";

export const apiBase = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

export async function fetchJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, { signal });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `API returned ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function postJson<T, B = unknown>(path: string, body?: B, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `API returned ${response.status}`);
  }
  return (await response.json()) as T;
}


export interface UseApiOptions<T>
  extends Omit<UseQueryOptions<T, Error, T, readonly [string]>, "queryKey" | "queryFn"> {
  enabled?: boolean;
}

export function useApi<T>(path: string, options?: UseApiOptions<T>): UseQueryResult<T, Error> {
  return useQuery({
    queryKey: [path] as const,
    queryFn: ({ signal }) => fetchJson<T>(path, signal),
    staleTime: 60_000,
    retry: 2,
    ...options,
  });
}
