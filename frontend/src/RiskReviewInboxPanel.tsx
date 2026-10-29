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
        borderRadius: "var(--radius)",
        bgcolor: "var(--bg)",
        boxShadow: "none",
        "&:before": { display: "none" },
      }}
    >
      <AccordionSummary
        sx={{
          px: "var(--space-3)",
          py: "var(--space-1)",
          bgcolor: "var(--line)",
          color: "var(--white)",
          borderBottom: "var(--border-width) solid var(--gray)",
          "&:focus-visible": {
            boxShadow: "none",
          },
        }}
      >
        <Stack
          direction={{ xs: "column", sm: "row" }}
          sx={{
            justifyContent: "space-between",
            alignItems: { xs: "flex-start", sm: "center" },
            width: "100%",
            pr: "var(--space-1)",
            gap: "var(--space-1)",
          }}
        >
          <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
            <Typography variant="h6" sx={{ fontWeight: 600, color: "var(--white)", fontSize: "var(--text-title)" }}>
              Risk Review Inbox
            </Typography>
            <Chip
              size="small"
              label={`${activeCount} Pending Review`}
              sx={{
                bgcolor: activeCount > 0 ? "var(--down)" : "var(--up)",
                color: "var(--white)",
                fontWeight: 600,
                borderRadius: "var(--radius)",
                fontSize: "var(--text-title)",
                height: 20,
              }}
            />
          </Stack>
          <Typography variant="caption" sx={{ color: "var(--gray)" }}>
            Audit trail of triggered threshold alerts with user sign-off
          </Typography>
        </Stack>
      </AccordionSummary>

      <AccordionDetails sx={{ p: "var(--space-3)", bgcolor: "var(--bg)" }}>
        {/* Filter Bar */}
        <Stack direction="row" spacing={1} sx={{ mb: "var(--space-3)", flexWrap: "wrap", gap: "var(--space-1)" }}>
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
                borderRadius: "var(--radius)",
                textTransform: "none",
                fontWeight: filter === tab.id ? 700 : 500,
                bgcolor: filter === tab.id ? "var(--up)" : "var(--line)",
                color: filter === tab.id ? "var(--bg)" : "var(--white)",
                boxShadow: "none",
                "&:hover": {
                  bgcolor: filter === tab.id ? "var(--up)" : "var(--white)",
                },
              }}
            >
              {tab.label}
            </Button>
          ))}
        </Stack>

        {/* Alerts List */}
        {filteredAlerts.length === 0 ? (
          <Box sx={{ p: "var(--space-4)", textAlign: "center", bgcolor: "var(--line)", borderRadius: "var(--radius)" }}>
            <Typography variant="body2" sx={{ color: "var(--gray)" }}>
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
                  p: "var(--space-3)",
                  borderRadius: "var(--radius)",
                  bgcolor:
                    alert.status === "active"
                      ? alert.severity === "critical"
                        ? "var(--gray)"
                        : "var(--bg)"
                      : "var(--line)",
                  boxShadow: "none",
                }}
              >
                <Stack
                  direction={{ xs: "column", sm: "row" }}
                  sx={{
                    justifyContent: "space-between",
                    alignItems: { xs: "flex-start", sm: "center" },
                    gap: "var(--space-2)",
                  }}
                >
                  <Box>
                    <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                      <Typography variant="subtitle1" sx={{ fontWeight: 600, color: "var(--white)" }}>
                        {alert.title}
                      </Typography>
                      <Chip
                        size="small"
                        label={alert.status.toUpperCase()}
                        sx={{
                          borderRadius: "var(--radius)",
                          fontSize: "var(--text-title)",
                          fontWeight: 600,
                          bgcolor:
                            alert.status === "active"
                              ? "var(--down)"
                              : alert.status === "reviewed"
                                ? "var(--up)"
                                : "var(--gray)",
                          color: "var(--white)",
                        }}
                      />
                    </Stack>
                    <Typography
                      variant="caption"
                      sx={{
                        color: "var(--gray)",
                        display: "block",
                        mt: "var(--space-1)",
                        fontFamily: "var(--font-data)",
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
                            borderRadius: "var(--radius)",
                            bgcolor: "var(--up)", color: "var(--line)",
                            textTransform: "none",
                            fontWeight: 600,
                            fontSize: "var(--text-title)",
                            px: "var(--space-2)",
                            boxShadow: "none",
                            "&:hover": { bgcolor: "var(--up)" },
                          }}
                        >
                          Mark Reviewed
                        </Button>
                        <Button
                          size="small"
                          onClick={() => handleStatusChange(alert.id, "dismissed")}
                          sx={{
                            borderRadius: "var(--radius)",
                            bgcolor: "var(--line)",
                            color: "var(--white)",
                            textTransform: "none",
                            fontWeight: 600,
                            fontSize: "var(--text-title)",
                            px: "var(--space-2)",
                            "&:hover": { bgcolor: "var(--white)" },
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
                          borderRadius: "var(--radius)",
                          bgcolor: "var(--bg)",
                          color: "var(--white)",
                          textTransform: "none",
                          fontWeight: 600,
                          fontSize: "var(--text-title)",
                          boxShadow: "none",
                          "&:hover": { bgcolor: "var(--line)" },
                        }}
                      >
                        Re-open Alert
                      </Button>
                    )}
                  </Stack>
                </Stack>

                <Typography variant="body2" sx={{ mt: "var(--space-2)", color: "var(--white)", fontSize: "var(--text-title)", lineHeight: "var(--leading)" }}>
                  {alert.explanation}
                </Typography>

                {alert.contributingHoldings && alert.contributingHoldings.length > 0 && (
                  <Stack direction="row" spacing={1} sx={{ mt: "var(--space-2)", alignItems: "center", flexWrap: "wrap", gap: "var(--space-1)" }}>
                    <Typography variant="caption" sx={{ color: "var(--gray)", fontWeight: 600 }}>
                      Contributing Holdings:
                    </Typography>
                    {alert.contributingHoldings.map((sym) => (
                      <Chip
                        key={sym}
                        size="small"
                        label={sym}
                        sx={{
                          borderRadius: "var(--radius)",
                          bgcolor: "var(--bg)",
                          color: "var(--white)",
                          fontWeight: 600,
                          fontSize: "var(--text-title)",
                        }}
                      />
                    ))}
                  </Stack>
                )}

                {alert.reviewNotes && (
                  <Box sx={{ mt: "var(--space-2)", p: "var(--space-2)", bgcolor: "var(--bg)", borderRadius: "var(--radius)" }}>
                    <Typography variant="caption" sx={{ color: "var(--up)", fontWeight: 600, display: "block" }}>
                      Reviewer Sign-off Note:
                    </Typography>
                    <Typography variant="body2" sx={{ color: "var(--white)", fontStyle: "italic", fontSize: "var(--text-title)" }}>
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
              borderRadius: "var(--radius)",
              bgcolor: "var(--bg)",
              boxShadow: "none",
              color: "var(--white)",
            },
          },
        }}
      >
        <DialogTitle sx={{ fontWeight: 600, pb: "var(--space-1)", color: "var(--white)" }}>
          Sign-Off on Risk Alert
          <Typography variant="caption" sx={{ display: "block", color: "var(--gray)" }}>
            {notesModalAlert?.title} (Trigger: {notesModalAlert?.currentValue} vs {notesModalAlert?.thresholdValue})
          </Typography>
        </DialogTitle>
        <DialogContent sx={{ pt: "var(--space-1)" }}>
          <Typography variant="body2" sx={{ color: "var(--gray)", mb: "var(--space-2)" }}>
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
        <DialogActions sx={{ p: "var(--space-2)", bgcolor: "var(--line)" }}>
          <Button onClick={() => setNotesModalAlert(null)} sx={{ color: "var(--white)", textTransform: "none" }}>
            Cancel
          </Button>
          <Button
            onClick={handleSaveNotes}
            sx={{
              bgcolor: "var(--up)", color: "var(--line)",
              textTransform: "none",
              fontWeight: 600,
              borderRadius: "var(--radius)",
              px: "var(--space-2)",
              "&:hover": { bgcolor: "var(--up)" },
            }}
          >
            Confirm Review
          </Button>
        </DialogActions>
      </Dialog>
    </Accordion>
  );
}
