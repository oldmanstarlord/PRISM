import { lazy, Suspense } from "react";
import { Box, CircularProgress } from "@mui/material";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import CompanyDetail from "./CompanyDetail";
import Dashboard from "./Dashboard";

const MstPage = lazy(() => import("./MstPage"));
const PortfolioManager = lazy(() => import("./PortfolioManager"));

const PageLoader = <Box sx={{ display: "grid", placeItems: "center", minHeight: "100vh" }}><CircularProgress /></Box>;

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/companies/:symbol" element={<CompanyDetail />} />
        <Route path="/mst" element={<Suspense fallback={PageLoader}><MstPage /></Suspense>} />
        <Route path="/portfolio" element={<Suspense fallback={PageLoader}><PortfolioManager /></Suspense>} />
        <Route path="/portfolio-demo" element={<Navigate to="/portfolio" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
