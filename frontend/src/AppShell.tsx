import { useCallback, useEffect, useState, type ReactNode } from "react";
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  Link as MuiLink,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import { Link, useLocation } from "react-router-dom";
import { fetchJson } from "./api";
import type { BenchmarkQuote } from "./types";

export interface AppShellProps {
  children: ReactNode;
  subtitle?: string;
  actions?: ReactNode;
}

const navItems = [
  { label: "Sector Divergence", path: "/" },
  { label: "Correlation MST", path: "/mst" },
  { label: "My Portfolio", path: "/portfolio" },
];

export default function AppShell({ children, subtitle, actions }: AppShellProps) {
  const location = useLocation();
  const [benchmark, setBenchmark] = useState<BenchmarkQuote | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [lastSync, setLastSync] = useState<string | null>(null);

  const fetchBenchmarkQuote = useCallback(async (forceRefresh = false) => {
    try {
      setIsSyncing(true);
      const url = `/market-data/benchmark${forceRefresh ? "?force_refresh=true" : ""}`;
      const data = await fetchJson<BenchmarkQuote>(url, new AbortController().signal);
      setBenchmark(data);
      setLastSync(new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }));
    } catch {
      // Keep existing data if available
    } finally {
      setIsSyncing(false);
    }
  }, []);

  // Initial load and 20s auto-refresh interval for up-to-date live market tracking
  useEffect(() => {
    void fetchBenchmarkQuote(false);
    const timer = setInterval(() => {
      void fetchBenchmarkQuote(false);
    }, 20_000);
    return () => clearInterval(timer);
  }, [fetchBenchmarkQuote]);

  const isCurrent = (path: string) => {
    if (path === "/") {
      return location.pathname === "/" || location.pathname.startsWith("/companies/");
    }
    return location.pathname === path || location.pathname.startsWith(`${path}/`);
  };

  const bmPrice = benchmark?.latest_price;
  const bmChange = benchmark?.change ?? 0;
  const bmChangePct = benchmark?.change_percent ?? 0;
  const isPositive = bmChange >= 0;

  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        bgcolor: "#F9EBD7",
        color: "#292D2A",
        "@media print": {
          bgcolor: "#F9EBD7",
          "& .no-print": { display: "none !important" },
          "& .MuiPaper-root": { boxShadow: "none", breakInside: "avoid" },
        },
      }}
    >
      {/* Shared Application Header */}
      <Box
        component="header"
        className="no-print"
        sx={{
          bgcolor: "#292D2A",
          color: "#F9EBD7",
          borderBottom: "none",
          position: "sticky",
          top: 0,
          zIndex: 1100,
          boxShadow: "0 4px 12px rgba(41,45,42,0.14)",
        }}
      >
        <Box
          sx={{
            width: "100%",
            boxSizing: "border-box",
            px: { xs: "14px", sm: "20px", md: "32px" },
            py: 0.8,
          }}
        >
          <Stack
            direction={{ xs: "column", sm: "row" }}
            sx={{
              gap: { xs: 1, sm: 1.5 },
              alignItems: { xs: "stretch", sm: "center" },
              justifyContent: "space-between",
            }}
          >
            {/* Brand Logo & Title */}
            <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
              <MuiLink
                component={Link}
                to="/"
                underline="none"
                color="inherit"
                sx={{ display: "flex", alignItems: "baseline", gap: 1 }}
              >
                <Typography
                  variant="h6"
                  component="h1"
                  sx={{
                    fontWeight: 700,
                    fontSize: "1.1rem",
                    letterSpacing: "-0.5px",
                    color: "#F9EBD7",
                    "&:hover": { color: "#DCE9DE" },
                    transition: "color 0.2s",
                  }}
                >
                  PRISM
                </Typography>
                <Typography
                  variant="caption"
                  sx={{
                    color: "#E3D7C4",
                    fontWeight: 500,
                    fontSize: "0.76rem",
                    display: { xs: "none", md: "inline" },
                  }}
                >
                  {subtitle ?? "Explainable NIFTY 200 market intelligence"}
                </Typography>
              </MuiLink>
            </Stack>

            {/* Live Benchmark Tracker Bar */}
            <Stack
              direction="row"
              spacing={1}
              sx={{
                alignItems: "center",
                bgcolor: "rgba(249, 235, 215, 0.08)",
                px: 1.5,
                py: 0.35,
                borderRadius: "4px",
                border: "1px solid rgba(227, 215, 196, 0.20)",
              }}
            >
              <Tooltip title="NIFTY 50 is the benchmark index representing 50 of the largest and most liquid Indian companies. Live quotes are streamed and refreshed automatically at 20-second intervals.">
                <Typography
                  variant="caption"
                  sx={{
                    color: "#E3D7C4",
                    fontWeight: 700,
                    fontSize: "0.74rem",
                    letterSpacing: "0.5px",
                    cursor: "help",
                  }}
                >
                  NIFTY 50:
                </Typography>
              </Tooltip>

              {bmPrice != null ? (
                <Stack direction="row" spacing={0.75} sx={{ alignItems: "center" }}>
                  <Typography
                    variant="caption"
                    sx={{
                      fontWeight: 800,
                      color: "#F9EBD7",
                      fontFamily: "monospace",
                      fontSize: "0.82rem",
                    }}
                  >
                    ₹{bmPrice.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </Typography>
                  <Chip
                    size="small"
                    label={`${isPositive ? "+" : ""}${bmChange.toFixed(2)} (${isPositive ? "+" : ""}${bmChangePct.toFixed(2)}%)`}
                    sx={{
                      height: 18,
                      fontSize: "0.68rem",
                      fontWeight: 800,
                      borderRadius: "2px",
                      bgcolor: isPositive ? "#DCE9DE" : "#F6D9CC",
                      color: isPositive ? "#046A38" : "#B8321A",
                      px: 0.2,
                    }}
                  />
                </Stack>
              ) : (
                <Typography variant="caption" sx={{ color: "#E3D7C4", fontSize: "0.72rem" }}>
                  Connecting market feed…
                </Typography>
              )}

              <Tooltip title={lastSync ? `Live quote verified. Auto-updating every 20s. Click to force instant live sync. Last updated: ${lastSync}` : "Auto-updating live quotes. Click to force sync."}>
                <IconButton
                  size="small"
                  onClick={() => void fetchBenchmarkQuote(true)}
                  disabled={isSyncing}
                  sx={{
                    p: 0.25,
                    color: "#DCE9DE",
                    "&:hover": { color: "#F9EBD7" },
                  }}
                  aria-label="Force refresh live quotes"
                >
                  {isSyncing ? (
                    <CircularProgress size={12} sx={{ color: "#046A38" }} />
                  ) : (
                    <Box
                      component="span"
                      sx={{
                        display: "inline-block",
                        width: 7,
                        height: 7,
                        borderRadius: "50%",
                        bgcolor: "#046A38",
                        boxShadow: "0 0 6px #046A38",
                      }}
                    />
                  )}
                </IconButton>
              </Tooltip>
            </Stack>

            {/* Navigation & Header Actions */}
            <Stack
              direction="row"
              spacing={0.75}
              sx={{
                alignItems: "center",
                flexWrap: "wrap",
                overflowX: "auto",
                pb: { xs: 0.5, sm: 0 },
              }}
            >
              {navItems.map((item) => {
                const active = isCurrent(item.path);
                return (
                  <Button
                    key={item.path}
                    component={Link}
                    to={item.path}
                    size="small"
                    sx={{
                      color: active ? "#F9EBD7" : "#E3D7C4",
                      bgcolor: active ? "#046A38" : "transparent",
                      fontWeight: active ? 700 : 500,
                      fontSize: "0.76rem",
                      px: 1.2,
                      py: 0.35,
                      borderRadius: 0,
                      textTransform: "none",
                      border: "none",
                      boxShadow: active ? "0 2px 6px rgba(41,45,42,0.10)" : "none",
                      "&:hover": {
                        bgcolor: active ? "#034d28" : "#E3D7C4",
                        color: active ? "#F9EBD7" : "#292D2A",
                      },
                      "&:focus-visible": {
                        boxShadow: "0 0 0 2px #046A38",
                      },
                      whiteSpace: "nowrap",
                    }}
                  >
                    {item.label}
                  </Button>
                );
              })}
              {actions && <Box sx={{ ml: { sm: 1 } }}>{actions}</Box>}
            </Stack>
          </Stack>
        </Box>
      </Box>

      {/* Main Content Area - Full screen width with compact side margins */}
      <Box
        component="main"
        sx={{
          flex: 1,
          width: "100%",
          boxSizing: "border-box",
          px: { xs: "14px", sm: "20px", md: "32px" },
          py: { xs: 1.5, sm: 2 },
        }}
      >
        {children}
      </Box>
    </Box>
  );
}
