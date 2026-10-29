import type { ReactNode } from "react";
import { Box } from "@mui/material";

export default function DetailsPanel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Box component="details" sx={{ borderTop: "1px solid #c9bfaf", borderBottom: "1px solid #c9bfaf", py: 1.5 }}>
      <Box component="summary" sx={{ cursor: "pointer", fontSize: "0.9375rem", fontWeight: 600, color: "#046A38", py: 0.5 }}>
        {title}
      </Box>
      <Box sx={{ pt: 2 }}>{children}</Box>
    </Box>
  );
}
