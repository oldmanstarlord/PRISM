import { useState, type FormEvent } from "react";
import type { Session } from "@supabase/supabase-js";
import {
  Alert,
  Box,
  Button,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { Navigate } from "react-router-dom";
import { useAuth } from "./authState";
import { apiBase } from "./api";
import { localLogin, storeLocalSession } from "./accountSession";
import { supabase } from "./supabase";

export default function LoginPage() {
  const { session, loading } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (loading)
    return (
      <Box role="status" sx={{ p: 4 }}>
        Loading account…
      </Box>
    );
  if (session) return <Navigate to="/portfolio" replace />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (localLogin) {
        const response = await fetch(`${apiBase}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: email.trim(), password }),
        });
        if (!response.ok) {
          const payload = (await response.json().catch(() => null)) as {
            detail?: string;
          } | null;
          throw new Error(
            typeof payload?.detail === "string"
              ? payload.detail
              : "Unable to sign in. Please try again.",
          );
        }
        storeLocalSession((await response.json()) as Session);
      } else {
        if (!supabase) throw new Error("Sign-in is not configured.");
        const { error } = await supabase.auth.signInWithPassword({
          email: email.trim(),
          password,
        });
        if (error) throw error;
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to sign in.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Box
      component="main"
      sx={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        px: 3,
        bgcolor: "background.default",
      }}
    >
      <Box
        component="form"
        onSubmit={(event) => void submit(event)}
        sx={{ width: "100%", maxWidth: 380 }}
      >
        <Stack spacing={3}>
          <Typography sx={{ fontSize: 18, fontWeight: 600 }}>PRISM</Typography>
          <Box>
            <Typography component="h1" sx={{ fontSize: 28, fontWeight: 600 }}>
              Sign in
            </Typography>
            <Typography color="text.secondary" sx={{ mt: 1 }}>
              Access your portfolio.
            </Typography>
          </Box>
          {error && <Alert severity="error">{error}</Alert>}
          <TextField
            label="Email"
            type="email"
            autoComplete="username"
            required
            fullWidth
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            disabled={busy}
          />
          <TextField
            label="Password"
            type="password"
            autoComplete="current-password"
            required
            fullWidth
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            disabled={busy}
          />
          <Button
            type="submit"
            variant="contained"
            disabled={busy}
            sx={{ minHeight: 44, boxShadow: "none" }}
          >
            {busy ? "Signing in…" : "Sign in"}
          </Button>
        </Stack>
      </Box>
    </Box>
  );
}
