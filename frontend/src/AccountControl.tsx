import { type FormEvent, useState } from "react";
import {
  Alert,
  Button,
  Dialog,
  DialogContent,
  DialogTitle,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useAuth } from "./authState";
import { supabase } from "./supabase";

export default function AccountControl() {
  const { session, loading } = useAuth();
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function authenticate(createAccount: boolean) {
    if (!supabase || busy) return;
    setBusy(true);
    setMessage(null);
    try {
      const { data, error } = createAccount
        ? await supabase.auth.signUp({ email, password })
        : await supabase.auth.signInWithPassword({ email, password });
      if (error) throw error;
      if (data.session) {
        setOpen(false);
        setPassword("");
      } else {
        setMessage("Check your email to confirm your account, then sign in.");
      }
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to sign in. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    if (!supabase) return;
    setBusy(true);
    setMessage(null);
    try {
      const { error } = await supabase.auth.signOut();
      if (error) throw error;
      setOpen(false);
      setPassword("");
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Unable to sign out.",
      );
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    event.stopPropagation();
    void authenticate(false);
  }

  return (
    <>
      <button
        type="button"
        className="terminal-button"
        disabled={loading}
        onClick={() => {
          setMessage(null);
          setOpen(true);
        }}
      >
        {session ? "Account" : "Sign in"}
      </button>
      <Dialog
        open={open}
        onClose={() => {
          if (!busy) {
            setOpen(false);
            setPassword("");
          }
        }}
        fullWidth
        maxWidth="xs"
        aria-labelledby="account-title"
      >
        <DialogTitle id="account-title">
          {session ? "Your account" : "Sign in to PRISM"}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            {message && (
              <Alert severity="info" role="status">
                {message}
              </Alert>
            )}
            {!supabase ? (
              <Alert severity="warning">
                Sign-in is not configured. Set VITE_SUPABASE_URL and
                VITE_SUPABASE_PUBLISHABLE_KEY in Vercel, then redeploy.
              </Alert>
            ) : session ? (
              <>
                <Typography>{session.user.email}</Typography>
                <Button disabled={busy} onClick={() => void signOut()}>
                  Sign out
                </Button>
              </>
            ) : (
              <form onSubmit={submit}>
                <Stack spacing={2}>
                  <Typography>
                    Sign in for account sync and portfolio news analysis. Your
                    local portfolio remains available without signing in.
                  </Typography>
                  <TextField
                    label="Email"
                    type="email"
                    autoComplete="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                  <TextField
                    label="Password"
                    type="password"
                    autoComplete="current-password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  <Button
                    type="submit"
                    variant="contained"
                    disabled={busy || !email || !password}
                  >
                    {busy ? "Please wait…" : "Sign in"}
                  </Button>
                  <Button
                    type="button"
                    disabled={busy || !email || password.length < 8}
                    onClick={() => void authenticate(true)}
                  >
                    Create account
                  </Button>
                </Stack>
              </form>
            )}
            <Button
              type="button"
              disabled={busy}
              onClick={() => {
                setOpen(false);
                setPassword("");
              }}
            >
              Close
            </Button>
          </Stack>
        </DialogContent>
      </Dialog>
    </>
  );
}
