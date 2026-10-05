import { lazy, Suspense } from "react";
import { Box, CircularProgress } from "@mui/material";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import CompanyDetail from "./CompanyDetail";
import Dashboard from "./Dashboard";
import { AuthProvider } from "./AuthContext";

const MstPage = lazy(() => import("./MstPage"));
const PortfolioPage = lazy(() => import("./PortfolioPage"));

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/companies/:symbol" element={<CompanyDetail />} />
          <Route path="/mst" element={<Suspense fallback={<Box sx={{ display: "grid", placeItems: "center", minHeight: "100vh" }}><CircularProgress /></Box>}><MstPage /></Suspense>} />
          <Route path="/portfolios" element={<Suspense fallback={<Box sx={{ display: "grid", placeItems: "center", minHeight: "100vh" }}><CircularProgress /></Box>}><PortfolioPage /></Suspense>} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
