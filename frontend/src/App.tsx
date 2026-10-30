import { lazy, Suspense } from "react";
import { Box, CircularProgress } from "@mui/material";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { useAuth } from "./authState";
import LoginPage from "./LoginPage";

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
      <AccountRoutes />
    </BrowserRouter>
  );
}

function AccountRoutes() {
  const { session, loading } = useAuth();
  const location = useLocation();
  if (loading) return PageLoader;
  if (location.pathname === "/login") return <LoginPage />;
  if (!session) return <Navigate to="/login" replace />;
  return (
    <Workspace
      key={session.user.id}
      renderPage={(url) => (
        <Routes location={url}>
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
                <PortfolioManager key={session.user.id} />
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
