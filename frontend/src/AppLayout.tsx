import {
  AppBar,
  Box,
  Button,
  Chip,
  Container,
  Divider,
  Stack,
  Toolbar,
  Typography,
} from "@mui/material";
import React from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useApi } from "./api";
import type { LimitationsResponse, MarketRegimeResponse, MetaResponse, OperationsFreshness } from "./types";

const DEFAULT_DISCLAIMER =
  "PRISM is descriptive risk and explanation, NOT price prediction and NOT investment advice. " +
  "No look-ahead anywhere. Every score, alert, forecast and scenario must show reason, inputs, " +
  "thresholds, method version, data age and limitations. MST/correlation is never presented as " +
  "causal. Shock simulation is a scenario, not a forecast.";

const NAV_ITEMS = [
  { label: "Sector Divergence", path: "/" },
  { label: "Industries", path: "/sectors" },
  { label: "MST", path: "/mst" },
  { label: "Portfolio", path: "/portfolio" },
  { label: "Stocks", path: "/stocks" },
  { label: "Macro", path: "/macro" },
  { label: "Policy Rules", path: "/policy-rules" },
  { label: "News", path: "/news" },
  { label: "Shock", path: "/shock" },
  { label: "Validation", path: "/validation" },
  { label: "Data Health", path: "/data-health" },
  { label: "Alerts", path: "/alerts" },
  { label: "Watchlists", path: "/watchlists" },
  { label: "Limitations", path: "/about/limitations" },
];

export interface AppLayoutProps {
  children?: React.ReactNode;
}

export function AppLayoutInner({ children }: AppLayoutProps) {
  const location = useLocation();
  const { data: meta } = useApi<MetaResponse>("/meta");
  const { data: regimeData } = useApi<MarketRegimeResponse>("/macro/regime/latest");
  const { data: freshness = [] } = useApi<OperationsFreshness[]>("/ops/freshness");
  const { data: limitations } = useApi<LimitationsResponse>("/about/limitations");
  const freshnessItems = Array.isArray(freshness) ? freshness : [];

  const disclaimerText = meta?.disclaimer ?? DEFAULT_DISCLAIMER;
  const platformName = meta?.platform ?? "PRISM";
  const authorityText = meta?.authority ?? "PRISM_SRS.md";
  const universeText = meta?.universe ?? "NIFTY 200";

  return (
    <Box sx={{ display: "flex", flexDirection: "column", minHeight: "100vh", bgcolor: "#f4f7f9" }}>
      {/* Top Header */}
      <AppBar position="static" sx={{ bgcolor: "#102b3a", boxShadow: "none" }}>
        <Container maxWidth="lg">
          <Toolbar disableGutters sx={{ py: 1.5, display: "flex", flexWrap: "wrap", gap: 2 }}>
            <Box component={Link} to="/" sx={{ textDecoration: "none", color: "inherit", mr: 3 }}>
              <Typography variant="h4" component="h1" sx={{ fontWeight: 800, letterSpacing: 1 }}>
                {platformName}
              </Typography>
              <Typography variant="caption" sx={{ color: "#b9d5df", display: "block" }}>
                Explainable {universeText} market & risk intelligence
              </Typography>
            </Box>

            {/* Navigation links */}
            <Stack direction="row" spacing={0.5} sx={{ flexWrap: "wrap", gap: 0.5 }}>
              {NAV_ITEMS.map((item) => {
                const isActive =
                  item.path === "/"
                    ? location.pathname === "/" || location.pathname.startsWith("/companies")
                    : location.pathname.startsWith(item.path);

                return (
                  <Button
                    key={item.path}
                    component={NavLink}
                    to={item.path}
                    size="small"
                    sx={{
                      color: isActive ? "#ffffff" : "#c1d3dc",
                      bgcolor: isActive ? "rgba(255, 255, 255, 0.12)" : "transparent",
                      fontWeight: isActive ? 700 : 500,
                      px: 1.5,
                      borderRadius: 1.5,
                      textTransform: "none",
                      fontSize: "0.875rem",
                      "&:hover": {
                        bgcolor: "rgba(255, 255, 255, 0.2)",
                        color: "#ffffff",
                      },
                    }}
                  >
                    {item.label}
                  </Button>
                );
              })}
            </Stack>
          </Toolbar>
        </Container>
      </AppBar>

      {/* Market Regime Banner (FR-F4, D5) */}
      {freshnessItems.some((item) => item.status === "stale") && (
        <Box sx={{ bgcolor: "#fff1f0", borderBottom: "1px solid #ffccc7", py: 1 }}>
          <Container maxWidth="lg"><Typography color="error.dark" sx={{ fontWeight: 700 }}>
            Stale data: {freshnessItems.filter((item) => item.status === "stale").map((item) => item.source_key).join(", ")}. Scores may not reflect the latest available source data.
          </Typography></Container>
        </Box>
      )}
      {regimeData && (
        <Box
          data-testid="regime-banner"
          sx={{
            bgcolor:
              regimeData.regime === "stressed"
                ? "#fff1f0"
                : regimeData.regime === "trending"
                ? "#fffbe6"
                : "#f6ffed",
            borderBottom: "1px solid",
            borderColor:
              regimeData.regime === "stressed"
                ? "#ffccc7"
                : regimeData.regime === "trending"
                ? "#ffe58f"
                : "#b7eb8f",
            py: 0.75,
          }}
        >
          <Container maxWidth="lg">
            <Stack
              direction={{ xs: "column", sm: "row" }}
              spacing={1.5}
              sx={{ alignItems: "center", justifyContent: "space-between" }}
            >
              <Stack direction="row" spacing={1.5} sx={{ alignItems: "center", flexWrap: "wrap", rowGap: 0.5 }}>
                <Chip
                  size="small"
                  label={`REGIME: ${regimeData.regime.toUpperCase()}`}
                  color={
                    regimeData.regime === "stressed"
                      ? "error"
                      : regimeData.regime === "trending"
                      ? "warning"
                      : "success"
                  }
                  sx={{ fontWeight: 800, letterSpacing: 0.5 }}
                />
                <Typography variant="body2" sx={{ fontWeight: 600, color: "#1f2937" }}>
                  As of {regimeData.as_of}
                </Typography>
                <Divider orientation="vertical" flexItem sx={{ display: { xs: "none", sm: "block" } }} />
                <Typography variant="caption" sx={{ color: "#4b5563" }}>
                  Realised Vol: <strong>{regimeData.features.realised_vol_percentile?.toFixed(1)}%ile</strong>
                </Typography>
                <Typography variant="caption" sx={{ color: "#4b5563" }}>
                  Corr: <strong>{regimeData.features.correlation_percentile?.toFixed(1)}%ile</strong>
                </Typography>
                {regimeData.features.india_vix !== undefined && (
                  <Typography variant="caption" sx={{ color: "#4b5563" }}>
                    VIX: <strong>{regimeData.features.india_vix.toFixed(1)}</strong>
                  </Typography>
                )}
                <Chip
                  size="small"
                  variant="outlined"
                  label={`Risk Multiplier: ${regimeData.features.regime_multiplier?.toFixed(2)}x`}
                  sx={{ fontWeight: 700, height: 22 }}
                />
                {regimeData.features.hysteresis_applied && (
                  <Chip
                    size="small"
                    variant="outlined"
                    color="info"
                    label="Hysteresis active"
                    sx={{ height: 22, fontSize: "0.7rem" }}
                  />
                )}
              </Stack>
              <Button
                component={Link}
                to="/macro"
                size="small"
                sx={{
                  textTransform: "none",
                  fontWeight: 600,
                  fontSize: "0.8rem",
                  py: 0.2,
                  px: 1,
                  color: "#102b3a",
                  "&:hover": { bgcolor: "rgba(16, 43, 58, 0.08)" },
                }}
              >
                Macro Sensitivities & Series →
              </Button>
            </Stack>
          </Container>
        </Box>
      )}

      {/* Main Content Area */}
      <Box component="main" sx={{ flexGrow: 1 }}>
        {children ?? <Outlet />}
      </Box>


      {/* Shared Footer with Mandatory Regulatory Disclaimer */}
      <Box component="footer" sx={{ bgcolor: "#e7edf2", py: 4, mt: 6, borderTop: "1px solid #d5dfe6" }}>
        <Container maxWidth="lg">
          <Stack spacing={1.5}>
            <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.6 }}>
              {disclaimerText}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              End-of-day prices; filings and news checked every {limitations?.filings_news_poll_minutes ?? 30} minutes.
            </Typography>

            <Divider sx={{ my: 0.5 }} />

            <Stack
              direction={{ xs: "column", sm: "row" }}
              spacing={1}
              sx={{ justifyContent: "space-between", alignItems: { sm: "center" } }}
            >
              <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
                PRISM does not provide investment advice.
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Authority: {authorityText} • Universe: {universeText}
              </Typography>
            </Stack>
          </Stack>
        </Container>
      </Box>
    </Box>
  );
}

export default function AppLayout({ children }: AppLayoutProps) {
  return <AppLayoutInner>{children}</AppLayoutInner>;
}
