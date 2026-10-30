import type { Session } from "@supabase/supabase-js";
import { supabase } from "./supabase";

export const localLogin = import.meta.env.VITE_LOCAL_AUTH_ENABLED === "true";
const KEY = "prism.account.session";
let accountId = "guest";

export function setAccountScope(id: string) {
  accountId = id;
}

export function readLocalSession(): Session | null {
  try {
    const session = JSON.parse(
      localStorage.getItem(KEY) ?? "null",
    ) as Session | null;
    return session?.access_token &&
      session.user?.id &&
      (session.expires_at ?? 0) > Date.now() / 1000
      ? session
      : null;
  } catch {
    return null;
  }
}

export async function currentSession(): Promise<Session | null> {
  if (localLogin) return readLocalSession();
  return supabase ? (await supabase.auth.getSession()).data.session : null;
}

export function storeLocalSession(session: Session) {
  localStorage.setItem(KEY, JSON.stringify(session));
  window.dispatchEvent(new Event("prism:auth"));
}

export async function signOut() {
  if (localLogin) localStorage.removeItem(KEY);
  else await supabase?.auth.signOut();
  sessionStorage.removeItem("prism.workspace.tabs");
  window.location.assign("/login");
}

export function accountStorageKey(key: string) {
  return `${key}:${localLogin ? (readLocalSession()?.user.id ?? "guest") : accountId}`;
}
