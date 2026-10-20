import { useState } from "react";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import {
  type RiskAlertRecord,
  updateAlertStatus,
  syncIndicatorsToInbox,
  loadRiskInboxAlerts,
} from "./riskInboxStorage";

interface RiskReviewInboxPanelProps {
  alerts?: RiskAlertRecord[];
  triggeredIndicators?: Array<{
    id: string;
    title: string;
    metric_name: string;
    current_value?: number;
    threshold_value: number;
    severity: string;
    observation_period: string;
    explanation: string;
    contributing_holdings?: string[];
    triggered: boolean;
  }>;
  onAlertsChange?: (updated: RiskAlertRecord[]) => void;
  portfolioId?: string;
}

export function RiskReviewInboxPanel({
  alerts: initialAlerts,
  triggeredIndicators,
  onAlertsChange,
  portfolioId,
}: RiskReviewInboxPanelProps) {
  const [internalAlerts, setInternalAlerts] = useState<RiskAlertRecord[]>(() => {
    if (initialAlerts) return initialAlerts;
    if (triggeredIndicators) {
      return syncIndicatorsToInbox(triggeredIndicators, portfolioId);
    }
    return loadRiskInboxAlerts(portfolioId);
  });

  const alerts = initialAlerts || internalAlerts || [];
  const [filter, setFilter] = useState<"all" | "active" | "reviewed" | "dismissed">("active");
  const [notesModalAlert, setNotesModalAlert] = useState<RiskAlertRecord | null>(null);
  const [notesText, setNotesText] = useState("");

  const activeCount = alerts.filter((a) => a.status === "active").length;
  const reviewedCount = alerts.filter((a) => a.status === "reviewed").length;
  const dismissedCount = alerts.filter((a) => a.status === "dismissed").length;

  const filteredAlerts = alerts.filter((a) => {
    if (filter === "all") return true;
    return a.status === filter;
  });

  const handleStatusChange = (
    alertId: string,
    newStatus: "active" | "reviewed" | "dismissed",
    notes?: string
  ) => {
    const updated = updateAlertStatus(alertId, newStatus, notes, portfolioId);
    setInternalAlerts(updated);
    onAlertsChange?.(updated);
  };

  const handleOpenNotes = (alert: RiskAlertRecord) => {
    setNotesModalAlert(alert);
    setNotesText(alert.reviewNotes || "");
  };

  const handleSaveNotes = () => {
    if (!notesModalAlert) return;
    handleStatusChange(notesModalAlert.id, "reviewed", notesText);
    setNotesModalAlert(null);
  };

  return (
    <Accordion
      defaultExpanded={activeCount > 0}
      elevation={0}
      sx={{
        borderRadius: 0,
        bgcolor: "#F9EBD7",
        boxShadow: "0 6px 16px rgba(41,45,42,0.14)",
        "&:before": { display: "none" },
      }}
    >
      <AccordionSummary
        sx={{
          px: 2.5,
          py: 1.25,
          bgcolor: "#E3D7C4",
          color: "#292D2A",
          borderBottom: "1px solid rgba(41,45,42,0.08)",
          "&:focus-visible": {
            boxShadow: "0 0 0 2px #046A38",
          },
        }}
      >
        <Stack
          direction={{ xs: "column", sm: "row" }}
          sx={{
            justifyContent: "space-between",
            alignItems: { xs: "flex-start", sm: "center" },
            width: "100%",
            pr: 1,
            gap: 1,
          }}
        >
          <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
            <Typography variant="h6" sx={{ fontWeight: 700, color: "#292D2A", fontSize: "1.05rem" }}>
              📥 Risk Review Inbox
            </Typography>
            <Chip
              size="small"
              label={`${activeCount} Pending Review`}
              sx={{
                bgcolor: activeCount > 0 ? "#E34222" : "#046A38",
                color: "#F9EBD7",
                fontWeight: 700,
                borderRadius: 0,
                fontSize: "0.72rem",
                height: 20,
              }}
            />
          </Stack>
          <Typography variant="caption" sx={{ color: "#686B64" }}>
            Audit trail of triggered threshold alerts with user sign-off
          </Typography>
        </Stack>
      </AccordionSummary>

      <AccordionDetails sx={{ p: 3, bgcolor: "#F9EBD7" }}>
        {/* Filter Bar */}
        <Stack direction="row" spacing={1} sx={{ mb: 2.5, flexWrap: "wrap", gap: 0.5 }}>
          {(
            [
              { id: "active" as const, label: `Pending Active (${activeCount})` },
              { id: "reviewed" as const, label: `Reviewed (${reviewedCount})` },
              { id: "dismissed" as const, label: `Dismissed (${dismissedCount})` },
              { id: "all" as const, label: `All Alerts (${alerts.length})` },
            ] as const
          ).map((tab) => (
            <Button
              key={tab.id}
              size="small"
              onClick={() => setFilter(tab.id)}
              sx={{
                borderRadius: 0,
                textTransform: "none",
                fontWeight: filter === tab.id ? 700 : 500,
                bgcolor: filter === tab.id ? "#046A38" : "#E3D7C4",
                color: filter === tab.id ? "#F9EBD7" : "#292D2A",
                boxShadow: filter === tab.id ? "0 2px 6px rgba(4,106,56,0.20)" : "none",
                "&:hover": {
                  bgcolor: filter === tab.id ? "#03532c" : "#d8cbbe",
                },
              }}
            >
              {tab.label}
            </Button>
          ))}
        </Stack>

        {/* Alerts List */}
        {filteredAlerts.length === 0 ? (
          <Box sx={{ p: 4, textAlign: "center", bgcolor: "#E3D7C4", borderRadius: 0 }}>
            <Typography variant="body2" sx={{ color: "#686B64" }}>
              {filter === "active"
                ? "No pending alerts in the inbox. All monitored parameters are within configured thresholds."
                : `No alerts found matching filter "${filter}".`}
            </Typography>
          </Box>
        ) : (
          <Stack spacing={2}>
            {filteredAlerts.map((alert) => (
              <Paper
                key={alert.id}
                elevation={0}
                sx={{
                  p: 2.5,
                  borderRadius: 0,
                  bgcolor:
                    alert.status === "active"
                      ? alert.severity === "critical"
                        ? "#F6D9CC"
                        : "#F9EBD7"
                      : "#E3D7C4",
                  boxShadow: "0 3px 8px rgba(41,45,42,0.10)",
                }}
              >
                <Stack
                  direction={{ xs: "column", sm: "row" }}
                  sx={{
                    justifyContent: "space-between",
                    alignItems: { xs: "flex-start", sm: "center" },
                    gap: 1.5,
                  }}
                >
                  <Box>
                    <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                      <Typography variant="subtitle1" sx={{ fontWeight: 750, color: "#292D2A" }}>
                        {alert.title}
                      </Typography>
                      <Chip
                        size="small"
                        label={alert.status.toUpperCase()}
                        sx={{
                          borderRadius: 0,
                          fontSize: "0.68rem",
                          fontWeight: 700,
                          bgcolor:
                            alert.status === "active"
                              ? "#B8321A"
                              : alert.status === "reviewed"
                              ? "#046A38"
                              : "#686B64",
                          color: "#F9EBD7",
                        }}
                      />
                    </Stack>
                    <Typography
                      variant="caption"
                      sx={{
                        color: "#686B64",
                        display: "block",
                        mt: 0.5,
                        fontFamily: "JetBrains Mono",
                      }}
                    >
                      Triggered: {new Date(alert.triggeredAt).toLocaleString("en-IN")} · Trigger:{" "}
                      <strong>{alert.currentValue}</strong> vs Threshold:{" "}
                      <strong>{alert.thresholdValue}</strong>
                    </Typography>
                  </Box>

                  {/* Actions */}
                  <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                    {alert.status === "active" ? (
                      <>
                        <Button
                          size="small"
                          onClick={() => handleOpenNotes(alert)}
                          sx={{
                            borderRadius: 0,
                            bgcolor: "#046A38",
                            color: "#F9EBD7",
                            textTransform: "none",
                            fontWeight: 600,
                            fontSize: "0.75rem",
                            px: 1.5,
                            boxShadow: "0 2px 5px rgba(4,106,56,0.20)",
                            "&:hover": { bgcolor: "#03532c" },
                          }}
                        >
                          ✓ Mark Reviewed
                        </Button>
                        <Button
                          size="small"
                          onClick={() => handleStatusChange(alert.id, "dismissed")}
                          sx={{
                            borderRadius: 0,
                            bgcolor: "#E3D7C4",
                            color: "#292D2A",
                            textTransform: "none",
                            fontWeight: 600,
                            fontSize: "0.75rem",
                            px: 1.5,
                            "&:hover": { bgcolor: "#d8cbbe" },
                          }}
                        >
                          Dismiss
                        </Button>
                      </>
                    ) : (
                      <Button
                        size="small"
                        onClick={() => handleStatusChange(alert.id, "active")}
                        sx={{
                          borderRadius: 0,
                          bgcolor: "#F9EBD7",
                          color: "#292D2A",
                          textTransform: "none",
                          fontWeight: 600,
                          fontSize: "0.75rem",
                          boxShadow: "0 1px 3px rgba(41,45,42,0.10)",
                          "&:hover": { bgcolor: "#E3D7C4" },
                        }}
                      >
                        Re-open Alert
                      </Button>
                    )}
                  </Stack>
                </Stack>

                <Typography variant="body2" sx={{ mt: 1.5, color: "#292D2A", fontSize: "0.85rem", lineHeight: 1.55 }}>
                  {alert.explanation}
                </Typography>

                {alert.contributingHoldings && alert.contributingHoldings.length > 0 && (
                  <Stack direction="row" spacing={1} sx={{ mt: 1.5, alignItems: "center", flexWrap: "wrap", gap: 0.5 }}>
                    <Typography variant="caption" sx={{ color: "#686B64", fontWeight: 700 }}>
                      Contributing Holdings:
                    </Typography>
                    {alert.contributingHoldings.map((sym) => (
                      <Chip
                        key={sym}
                        size="small"
                        label={sym}
                        sx={{
                          borderRadius: 0,
                          bgcolor: "#F9EBD7",
                          color: "#292D2A",
                          fontWeight: 600,
                          fontSize: "0.72rem",
                        }}
                      />
                    ))}
                  </Stack>
                )}

                {alert.reviewNotes && (
                  <Box sx={{ mt: 1.5, p: 1.5, bgcolor: "#F9EBD7", borderRadius: 0 }}>
                    <Typography variant="caption" sx={{ color: "#046A38", fontWeight: 700, display: "block" }}>
                      Reviewer Sign-off Note:
                    </Typography>
                    <Typography variant="body2" sx={{ color: "#292D2A", fontStyle: "italic", fontSize: "0.82rem" }}>
                      "{alert.reviewNotes}"
                    </Typography>
                  </Box>
                )}
              </Paper>
            ))}
          </Stack>
        )}
      </AccordionDetails>

      {/* Sign-off Review Notes Modal */}
      <Dialog
        open={Boolean(notesModalAlert)}
        onClose={() => setNotesModalAlert(null)}
        maxWidth="sm"
        fullWidth
        slotProps={{
          paper: {
            sx: {
              borderRadius: 0,
              bgcolor: "#F9EBD7",
              boxShadow: "0 18px 44px rgba(41,45,42,0.24)",
              color: "#292D2A",
            },
          },
        }}
      >
        <DialogTitle sx={{ fontWeight: 700, pb: 1, color: "#292D2A" }}>
          Sign-Off on Risk Alert
          <Typography variant="caption" sx={{ display: "block", color: "#686B64" }}>
            {notesModalAlert?.title} (Trigger: {notesModalAlert?.currentValue} vs {notesModalAlert?.thresholdValue})
          </Typography>
        </DialogTitle>
        <DialogContent sx={{ pt: 1 }}>
          <Typography variant="body2" sx={{ color: "#686B64", mb: 2 }}>
            Record analytical rationale, rebalancing intent, or reason for acknowledging this condition without portfolio adjustment.
          </Typography>
          <TextField
            autoFocus
            multiline
            rows={3}
            fullWidth
            label="Reviewer Notes / Action Plan"
            placeholder="e.g. Acknowledged concentration in HDFCBANK due to recent outperformance; maintaining position until monthly rebalance."
            value={notesText}
            onChange={(e) => setNotesText(e.target.value)}
          />
        </DialogContent>
        <DialogActions sx={{ p: 2, bgcolor: "#E3D7C4" }}>
          <Button onClick={() => setNotesModalAlert(null)} sx={{ color: "#292D2A", textTransform: "none" }}>
            Cancel
          </Button>
          <Button
            onClick={handleSaveNotes}
            sx={{
              bgcolor: "#046A38",
              color: "#F9EBD7",
              textTransform: "none",
              fontWeight: 700,
              borderRadius: 0,
              px: 2,
              "&:hover": { bgcolor: "#03532c" },
            }}
          >
            Confirm Review
          </Button>
        </DialogActions>
      </Dialog>
    </Accordion>
  );
}
