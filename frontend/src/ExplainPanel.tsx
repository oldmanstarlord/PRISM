import { Alert, Box, Paper, Stack, Typography } from "@mui/material";

interface ExplainPanelProps {
  title?: string;
  limitations: string[];
  sparseEdgesCount?: number;
}

export function ExplainPanel({
  title = "Method and Descriptive Limitations",
  limitations,
  sparseEdgesCount,
}: ExplainPanelProps) {
  return (
    <Paper sx={{ p: 3, borderLeft: "4px solid #16697a" }}>
      <Stack spacing={2}>
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 650 }}>
            {title}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            PRISM is descriptive risk intelligence, NOT investment advice and NOT price prediction.
          </Typography>
        </Box>

        <Stack spacing={1}>
          {limitations.map((item, idx) => (
            <Typography key={idx} variant="body2" color="text.primary">
              • {item}
            </Typography>
          ))}
        </Stack>

        {sparseEdgesCount !== undefined && (
          <Alert severity="warning" sx={{ mt: 1 }}>
            The Minimum Spanning Tree deliberately retains only {sparseEdgesCount} relationships out
            of thousands of pairwise combinations. A missing edge does NOT imply two stocks are
            uncorrelated, and an edge does NOT denote causal influence.
          </Alert>
        )}
      </Stack>
    </Paper>
  );
}
