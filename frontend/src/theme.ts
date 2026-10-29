import { createTheme } from "@mui/material/styles";
import { terminalToken } from "./terminalTokens";
import "./terminal.css";
const c = (name: string) => terminalToken(name);
const font = "var(--font-data)",
  label = "var(--font-label)";
export const SHADOWS = {
  control: "none",
  card: "none",
  panel: "none",
  dialog: "none",
  selected: "none",
  input: "none",
  focusRing: "none",
};
export const COLORS = {
  warmIvory: "var(--bg)",
  softCream: "var(--bg)",
  sandBeige: "var(--bg-raised)",
  deepCharcoal: "var(--white)",
  mutedGrey: "var(--gray)",
  emerald: "var(--up)",
  vermilion: "var(--down)",
  vermilionText: "var(--down)",
  paleSage: "var(--bg)",
  paleTerracotta: "var(--bg)",
  darkOchre: "var(--amber)",
  clusters: [
    "var(--amber)",
    "var(--cyan)",
    "var(--white)",
    "var(--up)",
    "var(--down)",
  ],
};
export const theme = createTheme({
  palette: {
    mode: "dark",
    primary: {
      main: c("--amber"),
      light: c("--yellow"),
      dark: c("--amber-dim"),
      contrastText: c("--bg"),
    },
    secondary: {
      main: c("--cyan"),
      light: c("--cyan"),
      dark: c("--cyan"),
      contrastText: c("--bg"),
    },
    success: {
      main: c("--up"),
      light: c("--up"),
      dark: c("--up"),
      contrastText: c("--bg"),
    },
    error: {
      main: c("--down"),
      light: c("--down"),
      dark: c("--down"),
      contrastText: c("--bg"),
    },
    warning: {
      main: c("--yellow"),
      light: c("--yellow"),
      dark: c("--amber"),
      contrastText: c("--bg"),
    },
    info: {
      main: c("--cyan"),
      light: c("--cyan"),
      dark: c("--cyan"),
      contrastText: c("--bg"),
    },
    background: { default: c("--bg"), paper: c("--bg") },
    text: {
      primary: c("--white"),
      secondary: c("--gray"),
      disabled: c("--gray"),
    },
    divider: c("--line"),
    action: {
      hover: c("--bg-hover"),
      selected: c("--amber"),
      disabled: c("--gray"),
      disabledBackground: c("--bg"),
    },
  },
  spacing: 2,
  shape: { borderRadius: 0 },
  typography: {
    fontFamily: font,
    fontSize: 11,
    allVariants: {
      lineHeight: "var(--leading)",
      letterSpacing: 0,
      fontWeight: 400,
    },
    h1: { fontFamily: label, fontSize: "var(--text-title)", fontWeight: 600 },
    h2: { fontFamily: label, fontSize: "var(--text-label)", fontWeight: 600 },
    h3: { fontFamily: label, fontSize: "var(--text-label)", fontWeight: 600 },
    h4: { fontFamily: label, fontSize: "var(--text-label)", fontWeight: 600 },
    h5: { fontFamily: label, fontSize: "var(--text-label)", fontWeight: 600 },
    h6: { fontFamily: label, fontSize: "var(--text-label)", fontWeight: 600 },
    body1: { fontSize: "var(--text-data)" },
    body2: { fontSize: "var(--text-data)" },
    caption: { fontSize: "var(--text-tag)", color: "var(--gray)" },
    overline: {
      fontFamily: label,
      fontSize: "var(--text-label)",
      textTransform: "none",
      color: "var(--amber)",
      fontWeight: 600,
    },
    button: {
      fontFamily: label,
      fontSize: "var(--text-tag)",
      fontWeight: 500,
      textTransform: "uppercase",
    },
  },
  components: {
    MuiCircularProgress: { defaultProps: { "aria-label": "Loading" } },
    MuiCssBaseline: {
      styleOverrides: {
        body: { background: "var(--bg)", color: "var(--white)" },
      },
    },
    MuiButtonBase: { defaultProps: { disableRipple: true } },
    MuiPaper: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: {
          border: "var(--border-width) solid var(--line)",
          background: "var(--bg)",
          backgroundImage: "none",
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          background: "var(--bg)",
          border: "var(--border-width) solid var(--line)",
        },
      },
    },
    MuiButton: {
      defaultProps: { size: "small", disableElevation: true },
      styleOverrides: {
        root: {
          border: "var(--border-width) solid var(--line-strong)",
          color: "var(--amber)",
          background: "var(--bg)",
        },
        contained: { color: "var(--bg)", background: "var(--amber)" },
      },
    },
    MuiTextField: { defaultProps: { size: "small" } },
    MuiFormControl: { defaultProps: { size: "small" } },
    MuiTableCell: {
      defaultProps: { size: "small" },
      styleOverrides: {
        root: {
          fontFamily: font,
          fontSize: "var(--text-data)",
          lineHeight: "var(--leading)",
          borderBottom: "var(--border-width) solid var(--line)",
        },
      },
    },
    MuiChip: {
      defaultProps: { size: "small" },
      styleOverrides: {
        root: {
          fontFamily: label,
          fontSize: "var(--text-tag)",
          border: "var(--border-width) solid currentColor",
          background: "var(--bg)",
        },
      },
    },
    MuiTooltip: {
      defaultProps: { arrow: false },
      styleOverrides: {
        tooltip: {
          fontSize: "var(--text-tag)",
          background: "var(--bg)",
          border: "var(--border-width) solid var(--amber)",
        },
      },
    },
    MuiDialog: {
      defaultProps: { transitionDuration: 0 },
      styleOverrides: {
        paper: {
          background: "var(--bg)",
          border: "var(--border-width) solid var(--line-strong)",
        },
      },
    },
    MuiAccordion: {
      styleOverrides: {
        root: { background: "var(--bg)", "&:before": { display: "none" } },
      },
    },
  },
});
