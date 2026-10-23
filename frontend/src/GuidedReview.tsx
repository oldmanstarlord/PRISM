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
          p: 0,
          m: 0,
          listStyle: "none",
          borderBottom: "1px solid",
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
                minHeight: 72,
                gap: 1.25,
                px: { xs: 0.5, sm: 2 },
                py: 2,
                justifyContent: "flex-start",
                borderBottom: "3px solid",
                borderColor:
                  activeStep === index ? "primary.main" : "transparent",
                color: activeStep === index ? "primary.main" : "text.secondary",
                "&.Mui-disabled": {
                  color:
                    activeStep === index ? "primary.main" : "text.disabled",
                },
                boxShadow: "none",
                fontSize: { xs: ".8125rem", sm: ".9375rem" },
                lineHeight: 1.4,
              }}
            >
              <Box
                component="span"
                aria-hidden="true"
                sx={{
                  display: "grid",
                  placeItems: "center",
                  flexShrink: 0,
                  width: 28,
                  height: 28,
                  bgcolor: activeStep === index ? "primary.main" : "#E3D7C4",
                  color: activeStep === index ? "#F9EBD7" : "text.secondary",
                }}
              >
                {index + 1}
              </Box>
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
        borderTop: "1px solid",
        borderColor: "divider",
        py: 2,
        "& > summary": {
          cursor: "pointer",
          color: "primary.main",
          fontWeight: 600,
          minHeight: 28,
          lineHeight: 1.8,
        },
      }}
    >
      <Box component="summary">{title}</Box>
      <Box sx={{ pt: 2 }}>{children}</Box>
    </Box>
  );
}

export function ReviewHeading({
  title,
  description,
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
        gap: 2,
        justifyContent: "space-between",
        alignItems: { sm: "center" },
      }}
    >
      <Box>
        <Typography variant={level === 1 ? "h1" : "h2"}>{title}</Typography>
        {description && (
          <Typography sx={{ mt: 1, maxWidth: "65ch", color: "text.secondary" }}>
            {description}
          </Typography>
        )}
      </Box>
      {action}
    </Stack>
  );
}
