import { useState, useId, type MouseEvent, type ReactNode } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  Drawer,
  IconButton,
  Popover,
  Snackbar,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import CheckIcon from "@mui/icons-material/Check";
import PrintIcon from "@mui/icons-material/Print";

import { useExplanation } from "../hooks/useExplain";
import type { ExplanationEvidence, ExplanationPayload } from "../types";
import { GlossaryTerm } from "./GlossaryTerm";

interface ExplainDrawerProps {
  open: boolean;
  symbol?: string;
  componentKey?: string;
  path?: string;
  onClose: () => void;
  payload?: ExplanationPayload;
}

// Map of keywords and phrases to their glossary term keys
const GLOSSARY_MAP: Array<{ regex: RegExp; termKey: string }> = [
  { regex: /\b(mst[- ]path decay|mst_path_decay)\b/gi, termKey: "mst_path_decay" },
  { regex: /\b(effective (?:number of )?bets)\b/gi, termKey: "effective_bets" },
  { regex: /\b(residual volatility)\b/gi, termKey: "residual_volatility" },
  { regex: /\b(sector divergence)\b/gi, termKey: "sector_divergence" },
  { regex: /\b(tree distance)\b/gi, termKey: "tree_distance" },
  { regex: /\b(score change)\b/gi, termKey: "score_change" },
  { regex: /\b(r[- ]squared|r2)\b/gi, termKey: "r_squared" },
  { regex: /\b(p[- ]value)\b/gi, termKey: "p_value" },
  { regex: /\b(z[- ]score)\b/gi, termKey: "z_score" },
  { regex: /\b(beta)\b/gi, termKey: "beta" },
  { regex: /\b(entropy)\b/gi, termKey: "entropy" },
  { regex: /\b(eigenvalues?)\b/gi, termKey: "eigenvalue" },
  { regex: /\b(concentration)\b/gi, termKey: "concentration" },
  { regex: /\b(centrality)\b/gi, termKey: "centrality" },
  { regex: /\b(degree)\b/gi, termKey: "degree" },
  { regex: /\b(shrinkage)\b/gi, termKey: "shrinkage" },
];

function renderWithGlossary(text: string, baseId: string): ReactNode {
  let segments: Array<{ text: string; termKey?: string }> = [{ text }];

  for (const { regex, termKey } of GLOSSARY_MAP) {
    const nextSegments: Array<{ text: string; termKey?: string }> = [];
    for (const seg of segments) {
      if (seg.termKey) {
        nextSegments.push(seg);
        continue;
      }
      regex.lastIndex = 0;
      let lastIndex = 0;
      let match: RegExpExecArray | null;
      while ((match = regex.exec(seg.text)) !== null) {
        if (match.index > lastIndex) {
          nextSegments.push({ text: seg.text.slice(lastIndex, match.index) });
        }
        nextSegments.push({ text: match[0], termKey });
        lastIndex = match.index + match[0].length;
      }
      if (lastIndex < seg.text.length) {
        nextSegments.push({ text: seg.text.slice(lastIndex) });
      }
    }
    segments = nextSegments;
  }

  return segments.map((seg, idx) => {
    if (seg.termKey) {
      return (
        <GlossaryTerm key={`${baseId}-gloss-${idx}-${seg.termKey}`} termKey={seg.termKey}>
          <Box
            component="span"
            sx={{
              textDecoration: "underline dotted",
              textDecorationColor: "primary.main",
              cursor: "help",
              fontWeight: 500,
            }}
          >
            {seg.text}
          </Box>
        </GlossaryTerm>
      );
    }
    return <span key={`${baseId}-text-${idx}`}>{seg.text}</span>;
  });
}

function formatExplanationText(payload: ExplanationPayload): string {
  const parts: string[] = [];
  const asOfStr = payload.data_age?.as_of ?? "N/A";
  parts.push(`As of: ${asOfStr}`);
  parts.push(
    `Confidence: ${payload.confidence.level.toUpperCase()} | Data Age: ${
      payload.data_age.days !== null ? `${payload.data_age.days}d` : "Unavailable"
    } | Template: ${payload.template_version}`
  );
  parts.push("");

  if (payload.summary_points.length > 0) {
    parts.push("SUMMARY:");
    payload.summary_points.forEach((s) => parts.push(`• ${s.text}`));
    parts.push("");
  }

  if (payload.sections.length > 0) {
    parts.push("SECTIONS:");
    payload.sections.forEach((sec) => {
      parts.push(`\n[${sec.title}]`);
      sec.sentences.forEach((s) => parts.push(`• ${s.text}`));
    });
    parts.push("");
  }

  if (payload.evidence.length > 0) {
    parts.push("EVIDENCE:");
    payload.evidence.forEach((ev) => {
      parts.push(`• ${ev.label}: ${ev.value ?? "N/A"} (${ev.source_table} / ${ev.source_ref})`);
    });
    parts.push("");
  }

  if (payload.limitations.length > 0) {
    parts.push("LIMITATIONS:");
    payload.limitations.forEach((lim) => parts.push(`• ${lim}`));
    parts.push("");
  }

  parts.push(`DISCLAIMER:\n${payload.disclaimer}`);
  return parts.join("\n");
}

export function ExplainDrawer({
  open,
  symbol,
  componentKey,
  path,
  onClose,
  payload: suppliedPayload,
}: ExplainDrawerProps) {
  const baseId = useId();
  const requestPath =
    path ??
    (symbol && componentKey
      ? `/explain/component/${encodeURIComponent(symbol)}/${encodeURIComponent(componentKey)}`
      : "");
  const query = useExplanation(requestPath, open && suppliedPayload === undefined);
  const payload = suppliedPayload ?? query.data;
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [selectedEvidence, setSelectedEvidence] = useState<ExplanationEvidence | null>(null);
  const [copied, setCopied] = useState(false);
  const [copyNotification, setCopyNotification] = useState(false);

  const openEvidence = (event: MouseEvent<HTMLElement>, item: ExplanationEvidence) => {
    setAnchor(event.currentTarget);
    setSelectedEvidence(item);
  };

  const handleCopyText = async () => {
    if (!payload) return;
    try {
      const text = formatExplanationText(payload);
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setCopyNotification(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      // Fallback
    }
  };

  const handlePrint = () => {
    window.print();
  };

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      onKeyDown={(e) => {
        if (e.key === "Escape") onClose();
      }}
      slotProps={{
        paper: {
          sx: {
            "@media print": {
              position: "static",
              width: "100% !important",
              boxShadow: "none",
              p: 0,
            },
          },
        },
      }}
    >
      <Box
        sx={{
          width: { xs: "100vw", sm: 580, md: 640 },
          maxWidth: "100vw",
          p: { xs: 2, sm: 3.5 },
          "@media print": {
            width: "100%",
            p: 2,
          },
        }}
        role="dialog"
        aria-modal="true"
        aria-label="Explanation"
      >
        <Stack spacing={2.5}>
          {/* Header & Controls */}
          <Stack
            direction="row"
            sx={{
              justifyContent: "space-between",
              alignItems: "flex-start",
              "@media print": {
                "& .no-print": { display: "none" },
              },
            }}
          >
            <Box sx={{ pr: 1 }}>
              <Typography variant="overline" color="text.secondary">
                Evidence-Bound Explanation
              </Typography>
              <Typography variant="h5" sx={{ fontWeight: 700, lineHeight: 1.25 }}>
                {payload?.headline ?? "Loading explanation"}
              </Typography>
            </Box>

            {/* Action buttons (hidden on print) */}
            <Stack direction="row" spacing={0.5} className="no-print" sx={{ flexShrink: 0 }}>
              {payload && (
                <>
                  <Tooltip title="Copy explanation as plain text with disclaimer">
                    <Button
                      size="small"
                      variant={copied ? "contained" : "outlined"}
                      color={copied ? "success" : "inherit"}
                      startIcon={copied ? <CheckIcon /> : <ContentCopyIcon />}
                      onClick={handleCopyText}
                      sx={{ textTransform: "none", fontSize: "0.8rem", px: 1.5 }}
                    >
                      {copied ? "Copied" : "Copy text"}
                    </Button>
                  </Tooltip>
                  <Tooltip title="Print explanation">
                    <IconButton size="small" onClick={handlePrint} aria-label="Print explanation">
                      <PrintIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </>
              )}
              <IconButton onClick={onClose} aria-label="Close explanation">
                <CloseIcon />
              </IconButton>
            </Stack>
          </Stack>

          {query.isLoading && !payload && (
            <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
              <CircularProgress />
            </Box>
          )}

          {query.error && !payload && (
            <Alert severity="error">{query.error.message}</Alert>
          )}

          {payload && (
            <>
              {/* Badges / Metadata */}
              <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", gap: 0.5 }}>
                <Chip
                  size="small"
                  label={`Confidence: ${payload.confidence.level}`}
                  color={
                    payload.confidence.level === "high"
                      ? "success"
                      : payload.confidence.level === "low"
                      ? "warning"
                      : "info"
                  }
                />
                <Chip
                  size="small"
                  label={
                    payload.data_age.days === null
                      ? "Data age unavailable"
                      : `Data age: ${payload.data_age.days}d`
                  }
                  variant="outlined"
                />
                <Chip
                  size="small"
                  label={`Template ${payload.template_version}`}
                  variant="outlined"
                />
              </Stack>

              {/* Summary Points */}
              <Stack spacing={1}>
                {payload.summary_points.map((sentence, index) => (
                  <Typography
                    key={`${baseId}-sum-${index}`}
                    variant="body1"
                    sx={{ lineHeight: 1.6 }}
                  >
                    {renderWithGlossary(sentence.text, `${baseId}-sum-${index}`)}
                  </Typography>
                ))}
              </Stack>

              {/* Sections */}
              {payload.sections.map((section) => (
                <Box
                  key={section.key}
                  data-section-key={section.key}
                  sx={{
                    p: 2,
                    borderRadius: 1.5,
                    bgcolor: "action.hover",
                    "@media print": { bgcolor: "transparent", p: 1 },
                  }}
                >
                  <Typography variant="h6" sx={{ fontWeight: 650, mb: 1, fontSize: "1.05rem" }}>
                    {section.title}
                  </Typography>
                  <Stack spacing={1}>
                    {section.sentences.map((sentence, index) => (
                      <Typography
                        key={`${baseId}-${section.key}-${index}`}
                        variant="body2"
                        sx={{ lineHeight: 1.6 }}
                      >
                        {renderWithGlossary(sentence.text, `${baseId}-${section.key}-${index}`)}
                      </Typography>
                    ))}
                  </Stack>
                  {section.chart_spec && <ChartSpec spec={section.chart_spec} />}
                </Box>
              ))}

              <Divider />

              {/* Evidence Chips */}
              <Box>
                <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700 }}>
                  Evidence Citations
                </Typography>
                <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", gap: 0.8 }}>
                  {payload.evidence.map((item) => (
                    <Chip
                      key={item.evidence_id}
                      size="small"
                      label={`${item.label}: ${String(item.value ?? "N/A")}`}
                      onClick={(event) => openEvidence(event, item)}
                      variant="outlined"
                      clickable
                      sx={{ fontSize: "0.78rem" }}
                    />
                  ))}
                </Stack>
              </Box>

              {/* Limitations Panel */}
              <Alert severity="warning" sx={{ borderRadius: 1.5 }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
                  Methodological Limitations
                </Typography>
                <Stack spacing={0.5}>
                  {payload.limitations.map((item, idx) => (
                    <Typography key={`${baseId}-lim-${idx}`} variant="body2" sx={{ fontSize: "0.85rem" }}>
                      • {renderWithGlossary(item, `${baseId}-lim-${idx}`)}
                    </Typography>
                  ))}
                </Stack>
              </Alert>

              {/* Regulatory Disclaimer */}
              <Alert severity="info" sx={{ borderRadius: 1.5 }}>
                <Typography variant="caption" sx={{ display: "block", fontStyle: "italic", lineHeight: 1.5 }}>
                  {payload.disclaimer}
                </Typography>
              </Alert>
            </>
          )}
        </Stack>
      </Box>

      {/* Evidence Popover Details */}
      <Popover
        open={Boolean(anchor && selectedEvidence)}
        anchorEl={anchor}
        onClose={() => {
          setAnchor(null);
          setSelectedEvidence(null);
        }}
        anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
      >
        {selectedEvidence && (
          <Stack spacing={0.5} sx={{ p: 2, maxWidth: 360 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
              {selectedEvidence.label}
            </Typography>
            <Typography variant="body2">
              Source: {selectedEvidence.source_table} / {selectedEvidence.source_ref}
            </Typography>
            <Typography variant="body2">
              Window: {selectedEvidence.window ?? "Not applicable"}
            </Typography>
            <Typography variant="body2">
              As of: {selectedEvidence.as_of}
            </Typography>
            {selectedEvidence.kind && (
              <Typography variant="caption" color="text.secondary">
                Kind: {selectedEvidence.kind}
              </Typography>
            )}
          </Stack>
        )}
      </Popover>

      {/* Copy notification */}
      <Snackbar
        open={copyNotification}
        autoHideDuration={2500}
        onClose={() => setCopyNotification(false)}
        message="Explanation copied to clipboard with disclaimer"
      />
    </Drawer>
  );
}

function ChartSpec({ spec }: { spec: Record<string, unknown> }) {
  const [descending, setDescending] = useState(true);
  const type = String(spec.type ?? "unknown");
  if (type === "rolling_correlation") {
    const windowDays = spec.window ? `${spec.window}-day` : "";
    return (
      <Box sx={{ mt: 1 }}>
        <Typography variant="caption" color="text.secondary">
          Rolling {windowDays} correlation
        </Typography>
      </Box>
    );
  }
  if (type === "affected_stocks_table") {
    const sourceRows = Array.isArray(spec.rows) ? spec.rows : [];
    const rows = sourceRows
      .filter((row): row is Record<string, unknown> => typeof row === "object" && row !== null)
      .sort((left, right) => (Number(right.exposure_score) - Number(left.exposure_score)) * (descending ? 1 : -1));
    return (
      <Box sx={{ overflowX: "auto", mt: 1 }}>
        <Button size="small" onClick={() => setDescending((value) => !value)}>
          Exposure {descending ? "highest first" : "lowest first"}
        </Button>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Symbol</TableCell>
              <TableCell align="right">Exposure Score</TableCell>
              <TableCell>Direction</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((row, idx) => (
              <TableRow key={String(row.symbol ?? idx)}>
                <TableCell>{String(row.symbol ?? "")}</TableCell>
                <TableCell align="right">{Number(row.exposure_score ?? 0).toFixed(2)}</TableCell>
                <TableCell>{String(row.transmission_direction ?? "")}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Box>
    );
  }
  return null;
}
