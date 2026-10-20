/**
 * Risk Review Inbox Storage & Audit Trail
 *
 * Persists triggered alerts from prudential monitoring indicators,
 * allowing users to track, review, and dismiss alerts with exact dates,
 * trigger values, and configured thresholds.
 */

export interface RiskAlertRecord {
  id: string;
  indicatorId: string;
  title: string;
  metricName: string;
  currentValue: number | string;
  thresholdValue: number | string;
  severity: "info" | "warning" | "critical";
  observationPeriod: string;
  explanation: string;
  contributingHoldings: string[];
  triggeredAt: string; // ISO UTC
  status: "active" | "reviewed" | "dismissed";
  reviewedAt?: string;
  reviewNotes?: string;
}

const INBOX_STORAGE_PREFIX = "prism_risk_review_inbox";

function getStorageKey(portfolioId?: string): string {
  return portfolioId ? `${INBOX_STORAGE_PREFIX}_${portfolioId}` : INBOX_STORAGE_PREFIX;
}

export function loadRiskInboxAlerts(portfolioId?: string): RiskAlertRecord[] {
  try {
    const raw = localStorage.getItem(getStorageKey(portfolioId));
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveRiskInboxAlerts(alerts: RiskAlertRecord[], portfolioId?: string): void {
  try {
    localStorage.setItem(getStorageKey(portfolioId), JSON.stringify(alerts));
  } catch {
    // Storage unavailable
  }
}

/**
 * Synchronize incoming triggered indicators with the persistent inbox.
 * Any newly triggered alert is added as "active" if not already present for today.
 */
export function syncIndicatorsToInbox(
  indicators: Array<{
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
  }>,
  portfolioId?: string
): RiskAlertRecord[] {
  const existing = loadRiskInboxAlerts(portfolioId);
  const today = new Date().toISOString().substring(0, 10);
  const existingMap = new Map(existing.map((a) => [a.id, a]));

  let modified = false;

  for (const ind of indicators) {
    if (!ind.triggered) continue;

    // Unique alert ID per indicator + current value + date
    const alertId = `${ind.id}_${ind.current_value ?? "trig"}_${today}`;
    if (!existingMap.has(alertId)) {
      const newAlert: RiskAlertRecord = {
        id: alertId,
        indicatorId: ind.id,
        title: ind.title,
        metricName: ind.metric_name,
        currentValue: ind.current_value ?? "Triggered",
        thresholdValue: ind.threshold_value,
        severity: (ind.severity as "info" | "warning" | "critical") || "warning",
        observationPeriod: ind.observation_period,
        explanation: ind.explanation,
        contributingHoldings: ind.contributing_holdings || [],
        triggeredAt: new Date().toISOString(),
        status: "active",
      };
      existingMap.set(alertId, newAlert);
      modified = true;
    }
  }

  const updated = Array.from(existingMap.values()).sort(
    (a, b) => new Date(b.triggeredAt).getTime() - new Date(a.triggeredAt).getTime()
  );

  if (modified) {
    saveRiskInboxAlerts(updated, portfolioId);
  }

  return updated;
}

export function updateAlertStatus(
  alertId: string,
  newStatus: "active" | "reviewed" | "dismissed",
  notes?: string,
  portfolioId?: string
): RiskAlertRecord[] {
  const alerts = loadRiskInboxAlerts(portfolioId);
  const updated = alerts.map((a) => {
    if (a.id === alertId) {
      return {
        ...a,
        status: newStatus,
        reviewedAt: newStatus !== "active" ? new Date().toISOString() : undefined,
        reviewNotes: notes !== undefined ? notes : a.reviewNotes,
      };
    }
    return a;
  });
  saveRiskInboxAlerts(updated, portfolioId);
  return updated;
}

export const loadRiskReviewInbox = loadRiskInboxAlerts;

export function markAlertReviewed(
  alertId: string,
  notes?: string,
  portfolioId?: string
): RiskAlertRecord | null {
  const updated = updateAlertStatus(alertId, "reviewed", notes, portfolioId);
  return updated.find((a) => a.id === alertId) || null;
}

export function markAlertDismissed(
  alertId: string,
  notes?: string,
  portfolioId?: string
): RiskAlertRecord | null {
  const updated = updateAlertStatus(alertId, "dismissed", notes, portfolioId);
  return updated.find((a) => a.id === alertId) || null;
}

export function clearInboxForTesting(portfolioId?: string): void {
  try {
    if (portfolioId) {
      localStorage.removeItem(getStorageKey(portfolioId));
    } else {
      for (let i = localStorage.length - 1; i >= 0; i--) {
        const key = localStorage.key(i);
        if (key && key.startsWith(INBOX_STORAGE_PREFIX)) {
          localStorage.removeItem(key);
        }
      }
    }
  } catch {
    // Ignore in tests
  }
}
