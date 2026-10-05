import {
  AppBar,
  Box,
  Button,
  Container,
  Divider,
  Stack,
  Toolbar,
  Typography,
} from "@mui/material";
import React from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useApi } from "./api";
import type { MetaResponse } from "./types";

const DEFAULT_DISCLAIMER =
  "PRISM is descriptive risk and explanation, NOT price prediction and NOT investment advice. " +
  "No look-ahead anywhere. Every score, alert, forecast and scenario must show reason, inputs, " +
  "thresholds, method version, data age and limitations. MST/correlation is never presented as " +
  "causal. Shock simulation is a scenario, not a forecast.";

const NAV_ITEMS = [
  { label: "Sector Divergence", path: "/" },
  { label: "MST", path: "/mst" },
  { label: "Portfolio", path: "/portfolio" },
  { label: "Stocks", path: "/stocks" },
  { label: "Shock", path: "/shock" },
  { label: "Validation", path: "/validation" },
  { label: "Data Health", path: "/data-health" },
];

export interface AppLayoutProps {
  children?: React.ReactNode;
}

export function AppLayoutInner({ children }: AppLayoutProps) {
  const location = useLocation();
  const { data: meta } = useApi<MetaResponse>("/meta");

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
