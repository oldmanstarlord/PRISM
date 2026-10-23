import { useEffect, useRef, useState, type ReactNode } from "react";
import { Box, Button, Link as MuiLink, Stack, Typography } from "@mui/material";
import { Link, useLocation } from "react-router-dom";
import { fetchJson } from "./api";
import type { BenchmarkQuote } from "./types";

export interface AppShellProps {
  children: ReactNode;
  subtitle?: string;
  actions?: ReactNode;
}
const navItems = [
  { label: "Markets", path: "/" },
  { label: "My portfolio", path: "/portfolio" },
  { label: "Network", path: "/mst" },
  { label: "News", path: "/news" },
];

export default function AppShell({ children, actions }: AppShellProps) {
  const location = useLocation();
  const main = useRef<HTMLElement>(null);
  const step = new URLSearchParams(location.search).get("step");
  useEffect(() => {
    main.current?.focus({ preventScroll: true });
    document.documentElement.scrollTop = 0;
  }, [location.pathname, step]);
  const [benchmark, setBenchmark] = useState<BenchmarkQuote | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    const refresh = () => {
      void fetchJson<BenchmarkQuote>(
        "/market-data/benchmark",
        controller.signal,
      )
        .then(setBenchmark)
        .catch(() => {});
    };
    refresh();
    const timer = setInterval(refresh, 20_000);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, []);
  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        bgcolor: "background.default",
        "@media print": {
          "& .no-print": { display: "none !important" },
          "& .MuiPaper-root": { boxShadow: "none", breakInside: "avoid" },
        },
      }}
    >
      <MuiLink
        href="#main-content"
        sx={{
          position: "absolute",
          top: -100,
          left: 16,
          zIndex: 1300,
          bgcolor: "background.default",
          p: 2,
          "&:focus": { top: 8 },
        }}
      >
        Skip to content
      </MuiLink>
      <Box
        component="header"
        className="no-print"
        sx={{ bgcolor: "#292D2A", color: "#F9EBD7" }}
      >
        <Stack
          direction="row"
          sx={{
            maxWidth: 1280,
            mx: "auto",
            px: { xs: 2, sm: 3, md: 4 },
            py: 2,
            alignItems: "center",
            gap: { xs: 2, md: 4 },
            flexWrap: "wrap",
          }}
        >
          <MuiLink
            component={Link}
            to="/"
            underline="none"
            color="inherit"
            sx={{
              fontWeight: 750,
              fontSize: "1.25rem",
              letterSpacing: ".12em",
            }}
          >
            PRISM
          </MuiLink>
          <Stack
            component="nav"
            aria-label="Main navigation"
            direction="row"
            sx={{
              gap: 0.5,
              order: { xs: 3, sm: 0 },
              width: { xs: "100%", sm: "auto" },
              flexWrap: "wrap",
            }}
          >
            {navItems.map((item) => {
              const active =
                item.path === "/"
                  ? location.pathname === "/" ||
                    location.pathname.startsWith("/companies/")
                  : location.pathname.startsWith(item.path);
              return (
                <Button
                  key={item.path}
                  component={Link}
                  to={item.path}
                  aria-current={active ? "page" : undefined}
                  sx={{
                    minHeight: 44,
                    px: 1.75,
                    fontSize: ".9375rem",
                    color: active ? "#F9EBD7" : "#E3D7C4",
                    bgcolor: active ? "primary.main" : "transparent",
                    boxShadow: "none",
                    "&:hover": {
                      bgcolor: active
                        ? "primary.dark"
                        : "rgba(227,215,196,.12)",
                    },
                  }}
                >
                  {item.label}
                </Button>
              );
            })}
          </Stack>
          {benchmark?.latest_price != null && (
            <Typography
              variant="body2"
              sx={{
                ml: "auto",
                display: { xs: "none", lg: "block" },
                color: "#E3D7C4",
                fontVariantNumeric: "tabular-nums",
              }}
            >
              NIFTY 50 ·{" "}
              {benchmark.latest_price.toLocaleString("en-IN", {
                maximumFractionDigits: 2,
              })}{" "}
              · {(benchmark.change_percent ?? 0) >= 0 ? "+" : ""}
              {(benchmark.change_percent ?? 0).toFixed(2)}%
            </Typography>
          )}
          {actions}
        </Stack>
      </Box>
      <Box
        component="main"
        id="main-content"
        ref={main}
        tabIndex={-1}
        sx={{
          "&:focus-visible": { boxShadow: "none !important", outline: "none" },
          flex: 1,
          width: "100%",
          maxWidth: 1200,
          mx: "auto",
          boxSizing: "border-box",
          minWidth: 0,
          px: { xs: 2, sm: 3, md: 4 },
          py: { xs: 3, md: 5 },
        }}
      >
        {children}
      </Box>
      <Box
        component="footer"
        sx={{
          maxWidth: 1200,
          width: "100%",
          mx: "auto",
          boxSizing: "border-box",
          px: { xs: 2, md: 4 },
          py: 3,
          borderTop: "1px solid",
          borderColor: "divider",
        }}
      >
        <Typography variant="caption">
          PRISM provides research tools and does not provide investment advice.
        </Typography>
      </Box>
    </Box>
  );
}
