import { useApi } from "../api";
import type { ExplanationPayload } from "../types";

export function useExplain(symbol: string, componentKey: string, enabled = true) {
  const path = `/explain/component/${encodeURIComponent(symbol)}/${encodeURIComponent(componentKey)}`;
  return useExplanation(path, enabled && symbol.length > 0 && componentKey.length > 0);
}

export function useExplanation(path: string, enabled = true) {
  return useApi<ExplanationPayload>(path || "/explain/unavailable", {
    enabled: enabled && path.length > 0,
  });
}
