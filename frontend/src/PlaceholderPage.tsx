import { Box, Button, Container, Stack, Typography } from "@mui/material";
import { Link } from "react-router-dom";
import { EmptyState } from "./components";

export interface PlaceholderPageProps {
  title: string;
  stepName?: string;
  description?: string;
}

export function PlaceholderPage({
  title,
  stepName = "a later step",
  description = "This module and its interactive intelligence workflows are scheduled for activation in a subsequent PRISM step.",
}: PlaceholderPageProps) {
  return (
    <Container maxWidth="lg" sx={{ py: 6 }}>
      <Stack spacing={3}>
        <Box>
          <Typography variant="h4" component="h1" sx={{ fontWeight: 700, color: "#102b3a" }}>
            {title}
          </Typography>
          <Typography color="text.secondary">
            Module registered in PRISM navigation architecture.
          </Typography>
        </Box>

        <EmptyState
          title={`Coming in ${stepName}`}
          description={description}
          action={
            <Button component={Link} to="/" variant="outlined">
              Return to Sector Divergence
            </Button>
          }
        />
      </Stack>
    </Container>
  );
}

export default PlaceholderPage;
