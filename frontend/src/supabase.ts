import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const publishableKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY as string | undefined;
const localAuthEnabled = import.meta.env.VITE_LOCAL_AUTH_ENABLED === "true";

export const supabaseConfigurationError =
  !localAuthEnabled && (!url || !publishableKey)
    ? "Copy frontend/.env.example to frontend/.env and configure the Supabase URL and publishable key."
    : null;

export const supabase =
  !localAuthEnabled && url && publishableKey
    ? createClient(url, publishableKey, {
        auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
      })
    : null;
