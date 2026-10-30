import type { Session } from "@supabase/supabase-js";
import { type ReactNode, useEffect, useMemo, useState } from "react";

import { AuthContext } from "./authState";
import { supabase } from "./supabase";
import {
  localLogin,
  readLocalSession,
  setAccountScope,
} from "./accountSession";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(localLogin || Boolean(supabase));

  useEffect(() => {
    const applySession = (next: Session | null) => {
      setAccountScope(next?.user.id ?? "guest");
      setSession(next);
    };
    if (localLogin) {
      let active = true;
      const refresh = () => {
        applySession(readLocalSession());
        setLoading(false);
      };
      const validate = async () => {
        const next = readLocalSession();
        if (!next) {
          if (active) refresh();
          return;
        }
        try {
          const response = await fetch(
            `${import.meta.env.VITE_API_URL ?? "/api/v1"}/auth/me`,
            {
              headers: { Authorization: `Bearer ${next.access_token}` },
            },
          );
          if (active) {
            applySession(response.status === 401 ? null : next);
            setLoading(false);
          }
        } catch {
          if (active) {
            applySession(next);
            setLoading(false);
          }
        }
      };
      void validate();
      window.addEventListener("prism:auth", refresh);
      window.addEventListener("storage", refresh);
      const timer = window.setInterval(() => void validate(), 30_000);
      return () => {
        active = false;
        window.removeEventListener("prism:auth", refresh);
        window.removeEventListener("storage", refresh);
        window.clearInterval(timer);
      };
    }
    if (!supabase) {
      setLoading(false);
      return;
    }
    void supabase.auth
      .getSession()
      .then(({ data }) => {
        applySession(data.session);
        setLoading(false);
      })
      .catch(() => {
        applySession(null);
        setLoading(false);
      });
    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      applySession(nextSession);
      setLoading(false);
    });
    return () => data.subscription.unsubscribe();
  }, []);

  const value = useMemo(() => ({ session, loading }), [session, loading]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
