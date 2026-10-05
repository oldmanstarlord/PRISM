import { Alert, Chip, Stack, Typography } from "@mui/material";

import type { MissingRiskComponent } from "../types";

export function MissingDataBanner({ components }: { components: MissingRiskComponent[] }) {
  if (components.length === 0) return null;

  return (
    <Alert severity="warning" sx={{ mb: 3 }}>
      <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
        Missing data lowered this score&apos;s coverage and confidence.
      </Typography>
      <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", gap: 1 }}>
        {components.map((component) => (
          <Chip
            key={component.component_id}
            size="small"
            label={`${component.name} (${component.dimension}): ${component.reason}`}
            variant="outlined"
          />
        ))}
      </Stack>
    </Alert>
  );
}
