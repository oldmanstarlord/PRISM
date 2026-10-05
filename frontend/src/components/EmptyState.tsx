import { Box, Paper, Typography } from "@mui/material";
import React from "react";

export interface EmptyStateProps {
  title?: string;
  description?: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
}

export function EmptyState({
  title = "No data available",
  description = "There are no records to display at this time.",
  action,
  icon,
}: EmptyStateProps) {
  return (
    <Paper
      variant="outlined"
      sx={{
        p: 4,
        textAlign: "center",
        bgcolor: "#fafbfc",
        borderColor: "#e1e6eb",
        borderRadius: 2,
      }}
    >
      {icon && <Box sx={{ mb: 1.5, color: "text.secondary" }}>{icon}</Box>}
      <Typography variant="h6" sx={{ fontWeight: 650, color: "#14212b", mb: 0.5 }}>
        {title}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 480, mx: "auto", mb: action ? 2 : 0 }}>
        {description}
      </Typography>
      {action && <Box sx={{ mt: 2 }}>{action}</Box>}
    </Paper>
  );
}
