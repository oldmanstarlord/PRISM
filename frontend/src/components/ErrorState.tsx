import { Alert, AlertTitle, Box, Button } from "@mui/material";

export interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
}

export function ErrorState({
  title = "Failed to load data",
  message = "An unexpected error occurred while communicating with the API.",
  onRetry,
}: ErrorStateProps) {
  return (
    <Alert
      severity="error"
      sx={{ my: 2 }}
      action={
        onRetry && (
          <Button color="inherit" size="small" onClick={onRetry}>
            Retry
          </Button>
        )
      }
    >
      <AlertTitle sx={{ fontWeight: 650 }}>{title}</AlertTitle>
      <Box sx={{ fontSize: "0.875rem" }}>{message}</Box>
    </Alert>
  );
}
