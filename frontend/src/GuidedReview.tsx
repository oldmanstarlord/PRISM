import type { ReactNode } from "react";
import { Box, Button, Stack, Typography } from "@mui/material";
import { Link } from "react-router-dom";

export interface ReviewStep {
  label: string;
  to?: string;
  disabled?: boolean;
}

export function GuidedSteps({
  steps,
  activeStep,
  onChange,
  label = "Review progress",
}: {
  steps: ReviewStep[];
  activeStep: number;
  onChange?: (index: number) => void;
  label?: string;
}) {
  return (
    <Box component="nav" aria-label={label}>
      <Box
        component="ol"
        sx={{
          display: "grid",
          gridTemplateColumns: `repeat(${steps.length}, minmax(0, 1fr))`,
          p: "var(--space-1)",
          m: "var(--space-1)",
          listStyle: "none",
          borderBottom: "var(--border-width) solid",
          borderColor: "divider",
        }}
      >
        {steps.map((step, index) => (
          <Box component="li" key={step.label}>
            <Button
              {...(step.to ? { component: Link, to: step.to } : {})}
              onClick={() => onChange?.(index)}
              disabled={step.disabled || (!step.to && !onChange)}
              aria-label={`${index + 1}. ${step.label}`}
              aria-current={activeStep === index ? "step" : undefined}
              sx={{
                width: "100%",
                minHeight: "var(--control-height)",
                gap: "var(--space-1)",
                px: "var(--space-2)",
                py: "var(--space-1)",
                justifyContent: "flex-start",
                borderBottom: "var(--border-width) solid",
                borderColor:
                  activeStep === index ? "primary.main" : "transparent",
                color: activeStep === index ? "primary.main" : "text.secondary",
                "&.Mui-disabled": {
                  color:
                    activeStep === index ? "primary.main" : "text.disabled",
                },
                boxShadow: "none",
                fontSize: "var(--text-title)",
                lineHeight: "var(--leading)",
              }}
            >
              {step.label}
            </Button>
          </Box>
        ))}
      </Box>
    </Box>
  );
}

export function ReviewDetails({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <Box
      component="details"
      sx={{
        borderTop: "var(--border-width) solid",
        borderColor: "divider",
        py: "var(--space-1)",
        "& > summary": {
          cursor: "pointer",
          color: "primary.main",
          fontWeight: 600,
          minHeight: "var(--panel-title-height)",
          lineHeight: "var(--leading)",
        },
      }}
    >
      <Box component="summary">{title}</Box>
      <Box sx={{ pt: "var(--space-2)" }}>{children}</Box>
    </Box>
  );
}

export function ReviewHeading({
  title,
  action,
  level = 1,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  level?: 1 | 2;
}) {
  return (
    <Stack
      direction={{ xs: "column", sm: "row" }}
      sx={{
        gap: "var(--space-2)",
        justifyContent: "space-between",
        alignItems: { sm: "center" },
      }}
    >
      <Box>
        <Typography variant={level === 1 ? "h1" : "h2"}>{title}</Typography>
      </Box>
      {action}
    </Stack>
  );
}
