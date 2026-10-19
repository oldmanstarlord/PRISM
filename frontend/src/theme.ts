import { createTheme } from "@mui/material/styles";

export const SHADOWS = {
  control: "0 3px 8px rgba(41,45,42,0.10)",
  card: "0 6px 16px rgba(41,45,42,0.14)",
  panel: "0 10px 28px rgba(41,45,42,0.18)",
  dialog: "0 18px 44px rgba(41,45,42,0.24)",
  selected: "0 8px 20px rgba(4,106,56,0.20)",
  input: "0 2px 6px rgba(41,45,42,0.08), inset 0 1px 2px rgba(41,45,42,0.06)",
  focusRing: "0 0 0 2px #046A38",
};

export const COLORS = {
  warmIvory: "#F9EBD7",
  softCream: "#F9EBD7", // Remapped to Warm Ivory: eliminates white patches
  sandBeige: "#E3D7C4",
  deepCharcoal: "#292D2A",
  mutedGrey: "#686B64",
  emerald: "#046A38",
  vermilion: "#E34222",
  vermilionText: "#B8321A",
  paleSage: "#DCE9DE",
  paleTerracotta: "#F6D9CC",
  darkOchre: "#8A5A00",
  // Specific data-series / MST clusters (never used for gains/losses):
  clusters: ["#1F6F78", "#6B3F69", "#3F5B7A", "#A0522D", "#6B7A2A"],
};

export const theme = createTheme({
  palette: {
    mode: "light",
    primary: {
      main: "#046A38",
      light: "#058b4a",
      dark: "#034d28",
      contrastText: "#F9EBD7",
    },
    secondary: {
      main: "#1F6F78",
      light: "#2b8e9a",
      dark: "#144e54",
      contrastText: "#F9EBD7",
    },
    success: {
      main: "#046A38",
      light: "#058b4a",
      dark: "#034d28",
      contrastText: "#F9EBD7",
    },
    error: {
      main: "#E34222",
      light: "#eb5d41",
      dark: "#b8321a",
      contrastText: "#F9EBD7",
    },
    warning: {
      main: "#8A5A00",
      light: "#b07400",
      dark: "#664300",
      contrastText: "#F9EBD7",
    },
    info: {
      main: "#3F5B7A",
      light: "#55799f",
      dark: "#2a3d53",
      contrastText: "#F9EBD7",
    },
    background: {
      default: "#F9EBD7",
      paper: "#F9EBD7",
    },
    text: {
      primary: "#292D2A",
      secondary: "#686B64",
    },
    divider: "rgba(41,45,42,0.06)",
    action: {
      hover: "#E3D7C4",
      selected: "rgba(4, 106, 56, 0.12)",
      disabled: "#A5A8A0",
      disabledBackground: "#E3D7C4",
    },
  },
  typography: {
    fontFamily: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    h1: { fontWeight: 700, letterSpacing: "-0.03em", color: "#292D2A" },
    h2: { fontWeight: 700, letterSpacing: "-0.025em", color: "#292D2A" },
    h3: { fontWeight: 700, letterSpacing: "-0.02em", color: "#292D2A" },
    h4: { fontWeight: 700, letterSpacing: "-0.015em", color: "#292D2A" },
    h5: { fontWeight: 700, letterSpacing: "-0.01em", color: "#292D2A" },
    h6: { fontWeight: 600, letterSpacing: "-0.005em", color: "#292D2A" },
    subtitle1: { fontWeight: 500, color: "#686B64" },
    subtitle2: { fontWeight: 600, color: "#686B64", fontSize: "0.875rem" },
    body1: { fontSize: "0.95rem", lineHeight: 1.6, fontWeight: 500, color: "#292D2A" },
    body2: { fontSize: "0.875rem", lineHeight: 1.5, fontWeight: 500, color: "#686B64" },
    overline: {
      fontSize: "0.75rem",
      fontWeight: 600,
      letterSpacing: "0.08em",
      textTransform: "uppercase",
      color: "#686B64",
    },
    button: {
      textTransform: "none",
      fontWeight: 600,
    },
  },
  shape: {
    borderRadius: 0,
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundColor: "#F9EBD7",
          color: "#292D2A",
          fontFamily: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          fontWeight: 500,
          margin: 0,
          padding: 0,
          "::-webkit-scrollbar": {
            width: 8,
            height: 8,
          },
          "::-webkit-scrollbar-track": {
            backgroundColor: "#F9EBD7",
            borderRadius: 0,
          },
          "::-webkit-scrollbar-thumb": {
            backgroundColor: "#E3D7C4",
            borderRadius: 0,
            "&:hover": {
              backgroundColor: "#686B64",
            },
          },
        },
        ":focus-visible": {
          outline: "none !important",
          boxShadow: "0 0 0 2px #046A38 !important",
        },
        "input:-webkit-autofill": {
          WebkitBoxShadow: "0 0 0 1000px #F9EBD7 inset !important",
          WebkitTextFillColor: "#292D2A !important",
        },
      },
    },
    MuiPaper: {
      defaultProps: {
        elevation: 0,
      },
      styleOverrides: {
        root: {
          borderRadius: 0,
          border: "none",
          backgroundColor: "#F9EBD7",
          color: "#292D2A",
          boxShadow: SHADOWS.card,
          transition: "box-shadow 0.2s ease",
        },
      },
    },
    MuiCard: {
      defaultProps: {
        elevation: 0,
      },
      styleOverrides: {
        root: {
          borderRadius: 0,
          border: "none",
          backgroundColor: "#F9EBD7",
          color: "#292D2A",
          boxShadow: SHADOWS.card,
        },
      },
    },
    MuiButton: {
      defaultProps: {
        disableElevation: true,
      },
      styleOverrides: {
        root: {
          borderRadius: 0,
          textTransform: "none",
          fontWeight: 600,
          padding: "7px 16px",
          transition: "all 0.15s ease-in-out",
          border: "none",
          "&:focus-visible": {
            boxShadow: SHADOWS.focusRing,
          },
        },
        contained: {
          backgroundColor: "#046A38",
          color: "#F9EBD7",
          boxShadow: SHADOWS.control,
          "&:hover": {
            backgroundColor: "#034d28",
            boxShadow: SHADOWS.card,
          },
          "&.MuiButton-containedError": {
            backgroundColor: "#E34222",
            color: "#F9EBD7",
            fontWeight: 700,
            "&:hover": {
              backgroundColor: "#b8321a",
            },
          },
        },
        outlined: {
          border: "none",
          backgroundColor: "#E3D7C4",
          color: "#292D2A",
          boxShadow: SHADOWS.control,
          "&:hover": {
            border: "none",
            backgroundColor: "#d8cabc",
          },
        },
        text: {
          color: "#046A38",
          "&:hover": {
            backgroundColor: "#E3D7C4",
          },
        },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: {
          borderRadius: 0,
          color: "#292D2A",
          "&:focus-visible": {
            boxShadow: SHADOWS.focusRing,
          },
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          borderRadius: 0,
          "& .MuiOutlinedInput-root": {
            borderRadius: 0,
            backgroundColor: "#E3D7C4",
            boxShadow: SHADOWS.input,
            "& fieldset": {
              border: "none",
            },
            "&:hover fieldset": {
              border: "none",
            },
            "&.Mui-focused": {
              boxShadow: `${SHADOWS.focusRing} !important`,
              "& fieldset": {
                border: "none",
              },
            },
          },
        },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          borderRadius: 0,
          backgroundColor: "#E3D7C4",
          color: "#292D2A",
          boxShadow: SHADOWS.input,
          "& fieldset": {
            border: "none",
          },
          "&:hover fieldset": {
            border: "none",
          },
          "&.Mui-focused": {
            boxShadow: `${SHADOWS.focusRing} !important`,
            "& fieldset": {
              border: "none",
            },
          },
        },
        notchedOutline: {
          border: "none",
        },
      },
    },
    MuiSelect: {
      styleOverrides: {
        root: {
          borderRadius: 0,
          backgroundColor: "#E3D7C4",
          color: "#292D2A",
          boxShadow: SHADOWS.input,
          "& fieldset": {
            border: "none",
          },
          "&.Mui-focused": {
            boxShadow: `${SHADOWS.focusRing} !important`,
          },
        },
      },
    },
    MuiMenu: {
      styleOverrides: {
        paper: {
          borderRadius: 0,
          border: "none",
          backgroundColor: "#F9EBD7",
          color: "#292D2A",
          boxShadow: SHADOWS.panel,
        },
      },
    },
    MuiMenuItem: {
      styleOverrides: {
        root: {
          borderRadius: 0,
          color: "#292D2A",
          fontWeight: 500,
          "&:hover": {
            backgroundColor: "#E3D7C4",
          },
          "&.Mui-selected": {
            backgroundColor: "#046A38",
            color: "#F9EBD7",
            "&:hover": {
              backgroundColor: "#034d28",
            },
          },
        },
      },
    },
    MuiDialog: {
      styleOverrides: {
        paper: {
          borderRadius: 0,
          border: "none",
          backgroundColor: "#F9EBD7",
          color: "#292D2A",
          boxShadow: SHADOWS.dialog,
        },
        container: {
          "& .MuiBackdrop-root": {
            backgroundColor: "rgba(41, 45, 42, 0.42)",
          },
        },
      },
    },
    MuiDialogTitle: {
      styleOverrides: {
        root: {
          fontWeight: 700,
          color: "#292D2A",
          borderBottom: "none",
          paddingBottom: "12px",
        },
      },
    },
    MuiDialogContent: {
      styleOverrides: {
        root: {
          borderTop: "none",
          borderBottom: "none",
          color: "#292D2A",
        },
        dividers: {
          borderTop: "none",
          borderBottom: "none",
        },
      },
    },
    MuiDialogActions: {
      styleOverrides: {
        root: {
          borderTop: "none",
          padding: "16px 24px",
        },
      },
    },
    MuiTableContainer: {
      styleOverrides: {
        root: {
          borderRadius: 0,
          border: "none",
          boxShadow: SHADOWS.card,
          backgroundColor: "#F9EBD7",
        },
      },
    },
    MuiTableHead: {
      styleOverrides: {
        root: {
          backgroundColor: "#E3D7C4",
          "& .MuiTableCell-root": {
            color: "#292D2A",
            fontWeight: 700,
            fontSize: "0.8rem",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
            borderBottom: "none",
            backgroundColor: "#E3D7C4",
          },
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderBottom: "none",
          fontSize: "0.875rem",
          padding: "13px 16px",
          color: "#292D2A",
          fontWeight: 500,
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          borderBottom: "none",
          "&:hover": {
            backgroundColor: "#F9EBD7",
          },
          "&:nth-of-type(even)": {
            backgroundColor: "#FAF3E8",
          },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 0,
          fontWeight: 600,
          fontSize: "0.78rem",
          border: "none",
          backgroundColor: "#E3D7C4",
          color: "#292D2A",
        },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: {
          borderRadius: 0,
          border: "none",
          boxShadow: SHADOWS.control,
          fontSize: "0.88rem",
          fontWeight: 500,
          "&.MuiAlert-colorSuccess": {
            backgroundColor: "#DCE9DE",
            color: "#046A38",
            "& .MuiAlert-icon": {
              color: "#046A38",
            },
          },
          "&.MuiAlert-colorError": {
            backgroundColor: "#F6D9CC",
            color: "#B8321A",
            "& .MuiAlert-icon": {
              color: "#E34222",
            },
          },
          "&.MuiAlert-colorWarning": {
            backgroundColor: "#E3D7C4",
            color: "#8A5A00",
            "& .MuiAlert-icon": {
              color: "#8A5A00",
            },
          },
          "&.MuiAlert-colorInfo": {
            backgroundColor: "#E3D7C4",
            color: "#292D2A",
            "& .MuiAlert-icon": {
              color: "#1F6F78",
            },
          },
        },
      },
    },
    MuiTooltip: {
      styleOverrides: {
        tooltip: {
          borderRadius: 0,
          backgroundColor: "#292D2A",
          color: "#F9EBD7",
          border: "none",
          boxShadow: SHADOWS.card,
          fontSize: "0.8rem",
          fontWeight: 500,
          padding: "6px 12px",
        },
        arrow: {
          color: "#292D2A",
        },
      },
    },
    MuiDivider: {
      styleOverrides: {
        root: {
          border: "none",
          height: "1px",
          backgroundColor: "rgba(41,45,42,0.06)",
        },
      },
    },
    MuiTabs: {
      styleOverrides: {
        root: {
          borderBottom: "none",
        },
        indicator: {
          height: 3,
          backgroundColor: "#046A38",
          borderRadius: 0,
        },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: {
          borderRadius: 0,
          textTransform: "none",
          fontWeight: 600,
          color: "#686B64",
          "&.Mui-selected": {
            color: "#046A38",
          },
          "&:focus-visible": {
            boxShadow: SHADOWS.focusRing,
          },
        },
      },
    },
    MuiSwitch: {
      styleOverrides: {
        root: {
          borderRadius: 0,
        },
        thumb: {
          borderRadius: 0,
          backgroundColor: "#292D2A",
        },
        track: {
          borderRadius: 0,
          backgroundColor: "#E3D7C4",
          opacity: 1,
        },
        switchBase: {
          "&.Mui-checked": {
            color: "#046A38",
            "& + .MuiSwitch-track": {
              backgroundColor: "#046A38 !important",
              opacity: 0.8,
            },
          },
        },
      },
    },
    MuiCheckbox: {
      styleOverrides: {
        root: {
          borderRadius: 0,
          color: "#686B64",
          "&.Mui-checked": {
            color: "#046A38",
          },
          "& .MuiSvgIcon-root": {
            borderRadius: 0,
          },
          "&:focus-visible": {
            boxShadow: SHADOWS.focusRing,
          },
        },
      },
    },
    MuiRadio: {
      styleOverrides: {
        root: {
          color: "#686B64",
          "&.Mui-checked": {
            color: "#046A38",
          },
          "&:focus-visible": {
            boxShadow: SHADOWS.focusRing,
          },
        },
      },
    },
    MuiBadge: {
      styleOverrides: {
        badge: {
          borderRadius: 0,
          fontWeight: 700,
        },
      },
    },
    MuiSkeleton: {
      styleOverrides: {
        root: {
          borderRadius: 0,
          backgroundColor: "#E3D7C4",
        },
      },
    },
    MuiAccordion: {
      styleOverrides: {
        root: {
          borderRadius: "0 !important",
          border: "none",
          backgroundColor: "#F9EBD7",
          boxShadow: SHADOWS.card,
          "&:before": {
            display: "none",
          },
        },
      },
    },
    MuiSnackbarContent: {
      styleOverrides: {
        root: {
          borderRadius: 0,
          border: "none",
          backgroundColor: "#292D2A",
          color: "#F9EBD7",
          boxShadow: SHADOWS.panel,
        },
      },
    },
    MuiToggleButton: {
      styleOverrides: {
        root: {
          borderRadius: 0,
          border: "none",
          backgroundColor: "#E3D7C4",
          color: "#292D2A",
          fontWeight: 600,
          "&.Mui-selected": {
            backgroundColor: "#046A38",
            color: "#F9EBD7",
            "&:hover": {
              backgroundColor: "#034d28",
            },
          },
        },
      },
    },
  },
});
