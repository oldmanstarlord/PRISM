import { type ReactNode } from "react";
import { Box, Button, Link as MuiLink, Stack, Typography } from "@mui/material";
import { Link, useLocation } from "react-router-dom";

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

  const isCurrent = (path: string) => {
    if (path === "/") {
      return location.pathname === "/" || location.pathname.startsWith("/companies/");
    }
    return location.pathname === path || location.pathname.startsWith(`${path}/`);
  };

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
