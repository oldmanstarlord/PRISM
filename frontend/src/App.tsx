import { lazy, Suspense } from "react";
import { Box, CircularProgress } from "@mui/material";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import AppLayout from "./AppLayout";
import CompanyDetail from "./CompanyDetail";
import Dashboard from "./Dashboard";
import DataHealthPage from "./DataHealthPage";

const MstPage = lazy(() => import("./MstPage"));
const PortfolioPage = lazy(() => import("./PortfolioPage"));
const StocksPage = lazy(() => import("./StocksPage"));
const StockDetailPage = lazy(() => import("./StockDetailPage"));
const MacroPage = lazy(() => import("./MacroPage"));
const ShockPage = lazy(() => import("./ShockPage"));
const PolicyRulesPage = lazy(() => import("./PolicyRulesPage"));
const ValidationPage = lazy(() => import("./ValidationPage"));
const AlertsPage = lazy(() => import("./AlertsPage"));
const WatchlistsPage = lazy(() => import("./WatchlistsPage"));
const LimitationsPage = lazy(() => import("./LimitationsPage"));
const SectorsPage = lazy(() => import("./SectorsPage"));
const NewsPage = lazy(() => import("./NewsPage"));

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
        <Route
          path="/sectors"
          element={
            <Suspense fallback={<LoadingFallback />}>
              <SectorsPage />
            </Suspense>
          }
        />
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
          path="/macro"
          element={
            <Suspense fallback={<LoadingFallback />}>
              <MacroPage />
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
          path="/policy-rules"
          element={
            <Suspense fallback={<LoadingFallback />}>
              <PolicyRulesPage />
            </Suspense>
          }
        />

        <Route
          path="/news"
          element={<Suspense fallback={<LoadingFallback />}><NewsPage /></Suspense>}
        />
        <Route
          path="/validation"
          element={
            <Suspense fallback={<LoadingFallback />}>
              <ValidationPage />
            </Suspense>
          }
        />
        <Route path="/data-health" element={<DataHealthPage />} />
        <Route path="/alerts" element={<Suspense fallback={<LoadingFallback />}><AlertsPage /></Suspense>} />
        <Route path="/watchlists" element={<Suspense fallback={<LoadingFallback />}><WatchlistsPage /></Suspense>} />
        <Route path="/about/limitations" element={<Suspense fallback={<LoadingFallback />}><LimitationsPage /></Suspense>} />
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
