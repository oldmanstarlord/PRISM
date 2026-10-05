import { Alert, Container, List, ListItem, ListItemText, Typography } from "@mui/material";

import { useApi } from "./api";
import type { LimitationsResponse } from "./types";

const REQUIRED = [
  "Not investment advice and not a price prediction.",
  "Prices are end-of-day, not real-time.",
  "Historical validation uses current membership and has survivorship bias.",
  "Source gaps and publication delays lower confidence.",
  "Correlation and MST relationships do not establish causation.",
  "Shock simulations are scenarios, not forecasts.",
];

export default function LimitationsPage() {
  const { data } = useApi<LimitationsResponse>("/about/limitations");
  return <Container maxWidth="md" sx={{ py: 4 }}>
    <Typography variant="h4" component="h1" sx={{ fontWeight: 800, mb: 2 }}>Limitations & Responsible Use</Typography>
    <Alert severity="warning">PRISM is descriptive risk software, not investment advice.</Alert>
    <List>{[...REQUIRED, ...(data?.limitations ?? [])].map((item) => <ListItem key={item}><ListItemText primary={item} /></ListItem>)}</List>
    <Typography variant="caption">Method: {data?.method_version ?? "operations-disclosure-v1"}</Typography>
  </Container>;
}
