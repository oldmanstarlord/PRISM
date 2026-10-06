import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";

import { useApi } from "./api";
import { ExplainDrawer } from "./components/ExplainDrawer";
import type { SectorOverviewResponse } from "./types";

export default function SectorsPage() {
  const { data, error, isLoading } = useApi<SectorOverviewResponse>("/sectors/overview");
  const [selectedIndustry, setSelectedIndustry] = useState("");

  return (
    <Box sx={{ maxWidth: 1300, mx: "auto", px: { xs: 2, sm: 3 }, py: 4 }}>
      <Typography variant="h4" component="h1" sx={{ fontWeight: 750 }}>
        Industry Trend Overview
      </Typography>
      <Typography color="text.secondary" sx={{ mt: 0.5, mb: 3 }}>
        Official stored Industry groups, daily adjusted closes, and Layer 1 divergence flags.
      </Typography>
      {isLoading && <CircularProgress />}
      {error && <Alert severity="error">{error.message}</Alert>}
      {data && (
        <>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Industry</TableCell>
                  <TableCell>20-day trend</TableCell>
                  <TableCell align="right">Return</TableCell>
                  <TableCell align="right">Positive breadth</TableCell>
                  <TableCell align="right">Dispersion</TableCell>
                  <TableCell align="right">Flagged / scored</TableCell>
                  <TableCell align="right">Explanation</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.items.map((item) => (
                  <TableRow key={item.industry} hover>
                    <TableCell sx={{ fontWeight: 650 }}>{item.industry}</TableCell>
                    <TableCell>
                      <Chip
                        label={item.trend}
                        size="small"
                        color={item.trend === "up" ? "success" : item.trend === "down" ? "warning" : "default"}
                      />
                    </TableCell>
                    <TableCell align="right">{item.return_20d === null ? "—" : `${item.return_20d.toFixed(2)}%`}</TableCell>
                    <TableCell align="right">{item.breadth === null ? "—" : `${item.breadth.toFixed(1)}%`}</TableCell>
                    <TableCell align="right">{item.dispersion === null ? "—" : `${item.dispersion.toFixed(2)} pp`}</TableCell>
                    <TableCell align="right">{item.flagged_count} / {item.stock_count}</TableCell>
                    <TableCell align="right">
                      <Button size="small" onClick={() => setSelectedIndustry(item.industry)}>
                        Why?
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          <Stack spacing={0.5} sx={{ mt: 2 }}>
            {data.limitations.map((item) => <Typography variant="caption" color="text.secondary" key={item}>{item}</Typography>)}
          </Stack>
        </>
      )}
      <ExplainDrawer
        open={Boolean(selectedIndustry)}
        path={selectedIndustry ? `/explain/sector/${encodeURIComponent(selectedIndustry)}` : ""}
        onClose={() => setSelectedIndustry("")}
      />
    </Box>
  );
}
