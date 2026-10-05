import { Chip, type ChipProps } from "@mui/material";

export interface StatusChipProps {
  status?: string | null;
  label?: string;
  size?: "small" | "medium";
  variant?: ChipProps["variant"];
}

const statusColorMap: Record<string, "success" | "warning" | "error" | "info" | "default"> = {
  approved: "success",
  active: "success",
  match: "success",
  normal: "default",
  pass: "success",
  connected: "success",

  draft: "warning",
  warning: "warning",
  moderate: "warning",
  lagging: "warning",
  missing_b: "warning",

  retired: "default",
  error: "error",
  mismatch: "error",
  extreme: "error",
  strong: "error",
  stale: "error",
  fail: "error",

  info: "info",
};

export function StatusChip({ status, label, size = "small", variant = "filled" }: StatusChipProps) {
  const norm = (status ?? "unknown").toLowerCase().trim();
  const color = statusColorMap[norm] ?? "default";
  const displayLabel = label ?? status ?? "Unknown";

  return (
    <Chip
      size={size}
      label={displayLabel}
      color={color}
      variant={variant}
      sx={{ fontWeight: 600, textTransform: "capitalize" }}
    />
  );
}
