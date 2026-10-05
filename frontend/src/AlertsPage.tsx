import { Alert, Card, CardContent, Chip, Container, Stack, Typography } from "@mui/material";

import { useApi } from "./api";
import type { ExplainableAlert } from "./types";

export default function AlertsPage() {
  const { data = [], error } = useApi<ExplainableAlert[]>("/alerts");
  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Typography variant="h4" component="h1" sx={{ fontWeight: 800, mb: 1 }}>
        Explainable Alerts
      </Typography>
      <Alert severity="info" sx={{ mb: 3 }}>
        Alerts describe risk conditions from end-of-day prices and timestamped evidence. They are not forecasts or investment advice.
      </Alert>
      {error && <Alert severity="error">Unable to load alerts: {error.message}</Alert>}
      <Stack spacing={2}>
        {data.map((item) => (
          <Card variant="outlined" key={item.id}>
            <CardContent>
              <Stack direction="row" spacing={1} sx={{ mb: 1, flexWrap: "wrap" }}>
                <Chip label={item.alert_type.replace(/_/g, " ")} color="warning" />
                <Chip label={`${item.subject_type}: ${item.subject_id}`} variant="outlined" />
                <Chip label={item.status} variant="outlined" />
              </Stack>
              <Typography sx={{ fontWeight: 700 }}>{item.reason}</Typography>
              <Typography variant="body2" color="text.secondary">
                {new Date(item.created_at).toLocaleString()} · Method explainable-alerts-v1 · Config {item.config_version}
              </Typography>
              <Typography component="pre" variant="caption" sx={{ whiteSpace: "pre-wrap", mt: 1 }}>
                {JSON.stringify(item.inputs_ref, null, 2)}
              </Typography>
            </CardContent>
          </Card>
        ))}
        {!error && data.length === 0 && <Alert severity="success">No open alerts.</Alert>}
      </Stack>
    </Container>
  );
}
