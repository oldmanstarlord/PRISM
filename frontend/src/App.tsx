import { lazy, Suspense } from "react";
import { Box, CircularProgress } from "@mui/material";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import AppLayout from "./AppLayout";
import CompanyDetail from "./CompanyDetail";
import Dashboard from "./Dashboard";
import DataHealthPage from "./DataHealthPage";
import PlaceholderPage from "./PlaceholderPage";

const MstPage = lazy(() => import("./MstPage"));
const PortfolioPage = lazy(() => import("./PortfolioPage"));
const StocksPage = lazy(() => import("./StocksPage"));
const StockDetailPage = lazy(() => import("./StockDetailPage"));
const ShockPage = lazy(() => import("./ShockPage"));

function LoadingFallback() {
  return (
    <Box sx={{ display: "grid", placeItems: "center", minHeight: "50vh" }}>
      <CircularProgress />
    </Box>
  );
}

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/sector-divergence" element={<Navigate to="/" replace />} />
        <Route path="/companies/:symbol" element={<CompanyDetail />} />
        <Route
          path="/mst"
          element={
            <Suspense fallback={<LoadingFallback />}>
              <MstPage />
            </Suspense>
          }
        />
        <Route
          path="/portfolio"
          element={
            <Suspense fallback={<LoadingFallback />}>
              <PortfolioPage />
            </Suspense>
          }
        />
        <Route
          path="/stocks"
          element={
            <Suspense fallback={<LoadingFallback />}>
              <StocksPage />
            </Suspense>
          }
        />
        <Route
          path="/stocks/:symbol"
          element={
            <Suspense fallback={<LoadingFallback />}>
              <StockDetailPage />
            </Suspense>
          }
        />
        <Route
          path="/shock"
          element={
            <Suspense fallback={<LoadingFallback />}>
              <ShockPage />
            </Suspense>
          }
        />

        <Route
          path="/validation"
          element={
            <PlaceholderPage
              title="Walk-Forward & Purged Validation"
              stepName="Step 7"
              description="Strict out-of-sample backtesting, purged k-fold cross-validation with embargo, and calibration surveillance without look-ahead."
            />
          }
        />
        <Route path="/data-health" element={<DataHealthPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

const appQueryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      staleTime: 60_000,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={appQueryClient}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
