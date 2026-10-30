import type { Session } from "@supabase/supabase-js";
import { type ReactNode, useEffect, useMemo, useState } from "react";

import { AuthContext } from "./authState";
import { supabase } from "./supabase";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(Boolean(supabase));

  useEffect(() => {
    if (!supabase) return;
    let active = true;
    let receivedEvent = false;
    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      receivedEvent = true;
      if (!active) return;
      setSession(nextSession);
      setLoading(false);
    });
    void supabase.auth
      .getSession()
      .then(({ data }) => {
        if (active && !receivedEvent) {
          setSession(data.session);
          setLoading(false);
        }
      })
      .catch(() => {
        if (active && !receivedEvent) {
          setSession(null);
          setLoading(false);
        }
      });
    return () => {
      active = false;
      data.subscription.unsubscribe();
    };
  }, []);

  const value = useMemo(() => ({ session, loading }), [session, loading]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
