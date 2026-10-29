import { type ReactNode, useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";

import AppShell from "./AppShell";

import { useAuth } from "./authState";
import { fetchAuthenticatedJson } from "./api";
import { parsePortfolioCsv } from "./portfolioCsv";
import { supabase, supabaseConfigurationError } from "./supabase";
import type {
  PortfolioAuditEvent,
  PortfolioDetail,
  PortfolioInputMode,
  PortfolioPreview,
  PortfolioSummary,
} from "./types";

function SignInPanel() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function authenticate(createAccount: boolean) {
    if (!supabase) return;
    setBusy(true);
    setMessage(null);
    const result = createAccount
      ? await supabase.auth.signUp({ email, password })
      : await supabase.auth.signInWithPassword({ email, password });
    setBusy(false);
    if (result.error) setMessage(result.error.message);
    else if (createAccount && !result.data.session) {
      setMessage("Account created. Check your email to confirm it before signing in.");
    }
  }

  return (
    <Paper sx={{ p: "var(--space-3)", maxWidth: 520, borderRadius: "var(--radius)", border: "none", bgcolor: "var(--bg)", boxShadow: "none" }}>
      <Stack spacing={2}>
        <Typography variant="h5" sx={{ fontWeight: 600, color: "var(--white)" }}>Sign in to portfolios</Typography>
        <Typography sx={{ color: "var(--gray)" }}>Portfolios are private to your Supabase account.</Typography>
        {message && <Alert severity="info" sx={{ borderRadius: "var(--radius)", bgcolor: "var(--bg)", color: "var(--white)" }}>{message}</Alert>}
        <TextField label="Email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} sx={{ bgcolor: "var(--bg)" }} />
        <TextField label="Password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} sx={{ bgcolor: "var(--bg)" }} />
        <Stack direction="row" spacing={1}>
          <Button variant="contained" disabled={busy || !email || !password} onClick={() => void authenticate(false)} sx={{ borderRadius: "var(--radius)", bgcolor: "var(--up)", color: "var(--line)" }}>Sign in</Button>
          <Button disabled={busy || !email || password.length < 8} onClick={() => void authenticate(true)} sx={{ borderRadius: "var(--radius)", border: "none", bgcolor: "var(--line)", color: "var(--white)", "&:hover": { bgcolor: "var(--up)", color: "var(--line)" } }}>Create account</Button>
        </Stack>
      </Stack>
    </Paper>
  );
}

export default function PortfolioPage() {
  const { session, loading } = useAuth();
  const [name, setName] = useState("");
  const [inputMode, setInputMode] = useState<PortfolioInputMode>("quantities");
  const [rows, setRows] = useState<Array<{ symbol: string; value: string }>>([]);
  const [preview, setPreview] = useState<PortfolioPreview | null>(null);
  const [portfolios, setPortfolios] = useState<PortfolioSummary[]>([]);
  const [auditEvents, setAuditEvents] = useState<PortfolioAuditEvent[]>([]);
  const [selected, setSelected] = useState<PortfolioDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function loadPortfolios(token: string) {
    const [portfolioResult, auditResult] = await Promise.all([
      fetchAuthenticatedJson<PortfolioSummary[]>("/portfolios", token),
      fetchAuthenticatedJson<PortfolioAuditEvent[]>("/portfolios/audit-events", token),
    ]);
    setPortfolios(portfolioResult);
    setAuditEvents(auditResult);
  }

  useEffect(() => {
    if (!session) return;
    void Promise.all([
      fetchAuthenticatedJson<PortfolioSummary[]>("/portfolios", session.access_token),
      fetchAuthenticatedJson<PortfolioAuditEvent[]>("/portfolios/audit-events", session.access_token),
    ])
      .then(([portfolioResult, auditResult]) => {
        setPortfolios(portfolioResult);
        setAuditEvents(auditResult);
      })
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : "Unable to load portfolios");
      });
  }, [session]);

  if (supabaseConfigurationError) return <Page><Alert severity="warning">{supabaseConfigurationError}</Alert></Page>;
  if (loading) return <Page><CircularProgress /></Page>;
  if (!session) return <Page><SignInPanel /></Page>;
  const accessToken = session.access_token;

  async function previewUpload() {
    setBusy(true); setError(null); setPreview(null);
    try {
      const result = await fetchAuthenticatedJson<PortfolioPreview>("/portfolios/preview", accessToken, {
        method: "POST", body: JSON.stringify({ input_mode: inputMode, rows }),
      });
      setPreview(result);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to preview portfolio");
    } finally { setBusy(false); }
  }

  async function savePortfolio() {
    if (!preview?.preview_fingerprint) return;
    setBusy(true); setError(null);
    try {
      const result = await fetchAuthenticatedJson<PortfolioDetail>("/portfolios", accessToken, {
        method: "POST",
        body: JSON.stringify({ name, input_mode: inputMode, rows, preview_fingerprint: preview.preview_fingerprint }),
      });
      setSelected(result); setPreview(null); setRows([]); setName("");
      await loadPortfolios(accessToken);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to save portfolio");
    } finally { setBusy(false); }
  }

  async function openPortfolio(id: string) {
    setError(null);
    try {
      setSelected(await fetchAuthenticatedJson<PortfolioDetail>(`/portfolios/${id}`, accessToken));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load portfolio");
    }
  }

  return (
    <Page>
      <Stack spacing={3}>
        <Stack direction={{ xs: "column", sm: "row" }} sx={{ justifyContent: "space-between", gap: "var(--space-2)" }}>
          <Box><Typography variant="h4" sx={{ fontWeight: 600, color: "var(--white)" }}>Private portfolios</Typography><Typography sx={{ color: "var(--gray)" }}>Signed in as {session.user.email}</Typography></Box>
          <Button onClick={() => void supabase?.auth.signOut()} sx={{ borderRadius: "var(--radius)", border: "none", bgcolor: "var(--line)", color: "var(--white)", "&:hover": { bgcolor: "var(--down)", color: "var(--white)" } }}>Sign out</Button>
        </Stack>
        {error && <Alert severity="error" sx={{ borderRadius: "var(--radius)", bgcolor: "var(--gray)", color: "var(--down)" }}>{error}</Alert>}
        <Paper sx={{ p: "var(--space-3)", borderRadius: "var(--radius)", border: "none", bgcolor: "var(--bg)", boxShadow: "none" }}><Stack spacing={2}>
          <Typography variant="h5" sx={{ fontWeight: 600, color: "var(--white)" }}>Upload holdings</Typography>
          <Alert severity="info" icon={false} sx={{ borderRadius: "var(--radius)", bgcolor: "var(--bg)", color: "var(--white)" }}>CSV header: <code>symbol,value</code>. Use decimal weights such as <code>0.25</code>. Use <code>CASH</code> for INR cash.</Alert>
          <TextField label="Portfolio name" value={name} onChange={(event) => setName(event.target.value)} sx={{ bgcolor: "var(--bg)" }} />
          <FormControl sx={{ bgcolor: "var(--bg)" }}><InputLabel id="portfolio-mode">Input mode</InputLabel><Select labelId="portfolio-mode" label="Input mode" value={inputMode} onChange={(event) => { setInputMode(event.target.value as PortfolioInputMode); setPreview(null); }}><MenuItem value="quantities">Quantities</MenuItem><MenuItem value="weights">Weights</MenuItem></Select></FormControl>
          <Button component="label" sx={{ borderRadius: "var(--radius)", border: "none", bgcolor: "var(--line)", color: "var(--white)", "&:hover": { bgcolor: "var(--up)", color: "var(--line)" } }}>Choose CSV<input hidden type="file" accept=".csv,text/csv" onChange={(event) => { const file = event.target.files?.[0]; if (!file) return; void file.text().then((text) => { setRows(parsePortfolioCsv(text)); setPreview(null); setError(null); }).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Unable to read CSV")); }} /></Button>
          <Typography variant="body2" sx={{ color: "var(--gray)" }}>{rows.length ? `${rows.length} rows loaded` : "No CSV loaded"}</Typography>
          <Button variant="contained" disabled={busy || !rows.length || !name.trim()} onClick={() => void previewUpload()} sx={{ borderRadius: "var(--radius)", bgcolor: "var(--up)", color: "var(--line)" }}>Preview validation</Button>
        </Stack></Paper>
        {preview && <Paper sx={{ p: "var(--space-3)", borderRadius: "var(--radius)", border: "none", bgcolor: "var(--bg)", boxShadow: "none" }}><Stack spacing={2}>
          <Typography variant="h5" sx={{ fontWeight: 600, color: "var(--white)" }}>Validation preview</Typography>
          {preview.errors.map((item) => <Alert key={item} severity="error" sx={{ borderRadius: "var(--radius)", bgcolor: "var(--gray)", color: "var(--down)" }}>{item}</Alert>)}
          {preview.warnings.map((item) => <Alert key={item} severity="warning" sx={{ borderRadius: "var(--radius)", bgcolor: "var(--line)", color: "var(--amber)" }}>{item}</Alert>)}
          <Typography sx={{ color: "var(--white)" }}>Valuation date: {preview.valuation_date ?? "unavailable"}</Typography>
          <HoldingsTable holdings={preview.holdings} mode={preview.input_mode} />
          {Number(preview.cash_value) > 0 && <Typography sx={{ color: "var(--white)" }}>Cash: {preview.cash_value}</Typography>}
          <Button variant="contained" disabled={busy || !preview.valid} onClick={() => void savePortfolio()} sx={{ borderRadius: "var(--radius)", bgcolor: "var(--up)", color: "var(--line)" }}>Confirm and save private snapshot</Button>
        </Stack></Paper>}
        <Paper sx={{ p: "var(--space-3)", borderRadius: "var(--radius)", border: "none", bgcolor: "var(--bg)", boxShadow: "none" }}><Typography variant="h5" gutterBottom sx={{ fontWeight: 600, color: "var(--white)" }}>Saved portfolios</Typography>{!portfolios.length ? <Typography sx={{ color: "var(--gray)" }}>No saved portfolios yet.</Typography> : <Stack spacing={1}>{portfolios.map((portfolio) => <Button key={portfolio.id} variant="text" sx={{ justifyContent: "space-between", borderRadius: "var(--radius)", color: "var(--white)", "&:hover": { bgcolor: "var(--line)" } }} onClick={() => void openPortfolio(portfolio.id)}>{portfolio.name}<span style={{ color: "var(--gray)" }}>{portfolio.holding_count} holdings · {portfolio.valuation_date}</span></Button>)}</Stack>}</Paper>
        <Paper sx={{ p: "var(--space-3)", borderRadius: "var(--radius)", border: "none", bgcolor: "var(--bg)", boxShadow: "none" }}>
          <Typography variant="h5" gutterBottom sx={{ fontWeight: 600, color: "var(--white)" }}>Recent audit history</Typography>
          {!auditEvents.length ? (
            <Typography sx={{ color: "var(--gray)" }}>No portfolio changes recorded yet.</Typography>
          ) : (
            <Stack spacing={1}>
              {auditEvents.slice(0, 10).map((event) => (
                <Box key={event.id} sx={{ pb: "var(--space-1)" }}>
                  <Typography sx={{ fontWeight: 600 }}>{event.event_type}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {new Date(event.created_at).toLocaleString()} · {event.entity_id}
                  </Typography>
                </Box>
              ))}
            </Stack>
          )}
        </Paper>
        {selected && <Paper sx={{ p: "var(--space-3)" }}><Typography variant="h5">{selected.name}</Typography><Typography color="text.secondary">Snapshot {selected.valuation_date} · {selected.input_mode}</Typography><HoldingsTable holdings={selected.holdings} mode={selected.input_mode} /></Paper>}
      </Stack>
    </Page>
  );
}

function HoldingsTable({ holdings, mode }: { holdings: PortfolioDetail["holdings"]; mode: PortfolioInputMode }) {
  return <Table size="small"><TableHead><TableRow><TableCell>Symbol</TableCell><TableCell>Company</TableCell><TableCell>Industry</TableCell><TableCell align="right">{mode === "weights" ? "Weight" : "Quantity"}</TableCell></TableRow></TableHead><TableBody>{holdings.map((holding) => <TableRow key={holding.security_id}><TableCell>{holding.symbol}</TableCell><TableCell>{holding.company_name}</TableCell><TableCell>{holding.industry ?? "—"}</TableCell><TableCell align="right">{holding.value}</TableCell></TableRow>)}</TableBody></Table>;
}

function Page({ children }: { children: ReactNode }) {
  return (
    <AppShell subtitle="Portfolio Management">
      {children}
    </AppShell>
  );
}
