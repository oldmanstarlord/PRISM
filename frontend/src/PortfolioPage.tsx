import { type ReactNode, useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Container,
  FormControl,
  InputLabel,
  Link as MuiLink,
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
import { Link } from "react-router-dom";

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
    <Paper sx={{ p: 3, maxWidth: 520 }}>
      <Stack spacing={2}>
        <Typography variant="h5">Sign in to portfolios</Typography>
        <Typography color="text.secondary">Portfolios are private to your Supabase account.</Typography>
        {message && <Alert severity="info">{message}</Alert>}
        <TextField label="Email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
        <TextField label="Password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
        <Stack direction="row" spacing={1}>
          <Button variant="contained" disabled={busy || !email || !password} onClick={() => void authenticate(false)}>Sign in</Button>
          <Button variant="outlined" disabled={busy || !email || password.length < 8} onClick={() => void authenticate(true)}>Create account</Button>
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
        <Stack direction={{ xs: "column", sm: "row" }} sx={{ justifyContent: "space-between", gap: 2 }}>
          <Box><Typography variant="h4">Private portfolios</Typography><Typography color="text.secondary">Signed in as {session.user.email}</Typography></Box>
          <Button variant="outlined" onClick={() => void supabase?.auth.signOut()}>Sign out</Button>
        </Stack>
        {error && <Alert severity="error">{error}</Alert>}
        <Paper sx={{ p: 3 }}><Stack spacing={2}>
          <Typography variant="h5">Upload holdings</Typography>
          <Alert severity="info" icon={false}>CSV header: <code>symbol,value</code>. Use decimal weights such as <code>0.25</code>. Use <code>CASH</code> for INR cash.</Alert>
          <TextField label="Portfolio name" value={name} onChange={(event) => setName(event.target.value)} />
          <FormControl><InputLabel id="portfolio-mode">Input mode</InputLabel><Select labelId="portfolio-mode" label="Input mode" value={inputMode} onChange={(event) => { setInputMode(event.target.value as PortfolioInputMode); setPreview(null); }}><MenuItem value="quantities">Quantities</MenuItem><MenuItem value="weights">Weights</MenuItem></Select></FormControl>
          <Button component="label" variant="outlined">Choose CSV<input hidden type="file" accept=".csv,text/csv" onChange={(event) => { const file = event.target.files?.[0]; if (!file) return; void file.text().then((text) => { setRows(parsePortfolioCsv(text)); setPreview(null); setError(null); }).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Unable to read CSV")); }} /></Button>
          <Typography variant="body2">{rows.length ? `${rows.length} rows loaded` : "No CSV loaded"}</Typography>
          <Button variant="contained" disabled={busy || !rows.length || !name.trim()} onClick={() => void previewUpload()}>Preview validation</Button>
        </Stack></Paper>
        {preview && <Paper sx={{ p: 3 }}><Stack spacing={2}>
          <Typography variant="h5">Validation preview</Typography>
          {preview.errors.map((item) => <Alert key={item} severity="error">{item}</Alert>)}
          {preview.warnings.map((item) => <Alert key={item} severity="warning">{item}</Alert>)}
          <Typography>Valuation date: {preview.valuation_date ?? "unavailable"}</Typography>
          <HoldingsTable holdings={preview.holdings} mode={preview.input_mode} />
          {Number(preview.cash_value) > 0 && <Typography>Cash: {preview.cash_value}</Typography>}
          <Button variant="contained" color="success" disabled={busy || !preview.valid} onClick={() => void savePortfolio()}>Confirm and save private snapshot</Button>
        </Stack></Paper>}
        <Paper sx={{ p: 3 }}><Typography variant="h5" gutterBottom>Saved portfolios</Typography>{!portfolios.length ? <Typography color="text.secondary">No saved portfolios yet.</Typography> : <Stack spacing={1}>{portfolios.map((portfolio) => <Button key={portfolio.id} variant="text" sx={{ justifyContent: "space-between" }} onClick={() => void openPortfolio(portfolio.id)}>{portfolio.name}<span>{portfolio.holding_count} holdings · {portfolio.valuation_date}</span></Button>)}</Stack>}</Paper>
        <Paper sx={{ p: 3 }}>
          <Typography variant="h5" gutterBottom>Recent audit history</Typography>
          {!auditEvents.length ? (
            <Typography color="text.secondary">No portfolio changes recorded yet.</Typography>
          ) : (
            <Stack spacing={1}>
              {auditEvents.slice(0, 10).map((event) => (
                <Box key={event.id} sx={{ borderBottom: "1px solid #e3e8eb", pb: 1 }}>
                  <Typography sx={{ fontWeight: 700 }}>{event.event_type}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {new Date(event.created_at).toLocaleString()} · {event.entity_id}
                  </Typography>
                </Box>
              ))}
            </Stack>
          )}
        </Paper>
        {selected && <Paper sx={{ p: 3 }}><Typography variant="h5">{selected.name}</Typography><Typography color="text.secondary">Snapshot {selected.valuation_date} · {selected.input_mode}</Typography><HoldingsTable holdings={selected.holdings} mode={selected.input_mode} /></Paper>}
      </Stack>
    </Page>
  );
}

function HoldingsTable({ holdings, mode }: { holdings: PortfolioDetail["holdings"]; mode: PortfolioInputMode }) {
  return <Table size="small"><TableHead><TableRow><TableCell>Symbol</TableCell><TableCell>Company</TableCell><TableCell>Industry</TableCell><TableCell align="right">{mode === "weights" ? "Weight" : "Quantity"}</TableCell></TableRow></TableHead><TableBody>{holdings.map((holding) => <TableRow key={holding.security_id}><TableCell>{holding.symbol}</TableCell><TableCell>{holding.company_name}</TableCell><TableCell>{holding.industry ?? "—"}</TableCell><TableCell align="right">{holding.value}</TableCell></TableRow>)}</TableBody></Table>;
}

function Page({ children }: { children: ReactNode }) {
  return <Box sx={{ minHeight: "100vh", bgcolor: "#f4f7f9" }}><Box sx={{ bgcolor: "#102b3a", color: "white", py: 3 }}><Container maxWidth="lg"><Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between" }}><Typography variant="h3" sx={{ fontWeight: 700 }}>PRISM</Typography><MuiLink component={Link} to="/" color="inherit">Market intelligence</MuiLink></Stack></Container></Box><Container maxWidth="lg" sx={{ py: 4 }}>{children}</Container></Box>;
}
