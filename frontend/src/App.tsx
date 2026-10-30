import { lazy, Suspense } from "react";
import { Box, CircularProgress } from "@mui/material";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from "react-router-dom";

import Workspace from "./Workspace";
import CompanyDetail from "./CompanyDetail";
import Dashboard from "./Dashboard";

const MstPage = lazy(() => import("./MstPage"));
const PortfolioManager = lazy(() => import("./PortfolioManager"));
const NewsIntelligencePage = lazy(() => import("./NewsIntelligence"));

const PageLoader = (
  <Box sx={{ display: "grid", placeItems: "center", minHeight: "100vh" }}>
    <CircularProgress />
  </Box>
);

export default function App() {
  return (
    <BrowserRouter>
      <WorkspaceRoutes />
    </BrowserRouter>
  );
}

function WorkspaceRoutes() {
  return (
    <Workspace
      renderPage={(url) => (
        <Routes location={url}>
          <Route path="/login" element={<Navigate to="/portfolio" replace />} />
          <Route path="/" element={<Dashboard />} />
          <Route
            path="/news"
            element={
              <Suspense fallback={PageLoader}>
                <NewsIntelligencePage />
              </Suspense>
            }
          />
          <Route path="/companies/:symbol" element={<CompanyDetail />} />
          <Route
            path="/mst"
            element={
              <Suspense fallback={PageLoader}>
                <MstPage />
              </Suspense>
            }
          />
          <Route
            path="/portfolio"
            element={
              <Suspense fallback={PageLoader}>
                <PortfolioManager />
              </Suspense>
            }
          />
          <Route
            path="/portfolio-demo"
            element={<Navigate to="/portfolio" replace />}
          />
        </Routes>
      )}
    />
  );
}
