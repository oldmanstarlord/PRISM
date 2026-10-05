import { useState } from "react";
import { Chip, Tooltip } from "@mui/material";

export interface FreshnessBadgeProps {
  dataThroughDate?: string | null;
  ageDays?: number | null;
  asOf?: string | null;
  label?: string;
  size?: "small" | "medium";
}

export function FreshnessBadge({
  dataThroughDate,
  ageDays,
  asOf,
  label,
  size = "small",
}: FreshnessBadgeProps) {
  const [now] = useState(() => Date.now());
  const displayDate = dataThroughDate ?? asOf ?? "Unknown";

  let computedAge = ageDays;
  if (computedAge === undefined || computedAge === null) {
    if (dataThroughDate) {
      const dt = new Date(dataThroughDate);
      if (!isNaN(dt.getTime())) {
        const diffMs = now - dt.getTime();
        computedAge = Math.max(0, Math.floor(diffMs / (1000 * 60 * 60 * 24)));
      }
    }
  }

  let color: "success" | "warning" | "error" | "default" = "default";
  let statusText = "fresh";

  if (computedAge !== undefined && computedAge !== null) {
    if (computedAge <= 1) {
      color = "success";
      statusText = "fresh (<=1d)";
    } else if (computedAge < 5) {
      color = "warning";
      statusText = `lagging (${computedAge}d)`;
    } else {
      color = "error";
      statusText = `stale (${computedAge}d >= 5d)`;
    }
  }

  const chipLabel = label ? `${label}: ${displayDate}` : `Data: ${displayDate}`;
  const tooltipTitle = `Status: ${statusText}${computedAge !== undefined && computedAge !== null ? ` • Age: ${computedAge} day${computedAge === 1 ? "" : "s"}` : ""}`;

  return (
    <Tooltip title={tooltipTitle} arrow>
      <Chip
        size={size}
        label={chipLabel}
        color={color}
        variant="outlined"
        sx={{ fontWeight: 600, fontSize: "0.75rem" }}
      />
    </Tooltip>
  );
}
