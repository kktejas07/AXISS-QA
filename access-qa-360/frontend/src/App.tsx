import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { LoginPage } from "./pages/LoginPage";
import { Dashboard } from "./pages/Dashboard";
import { ProjectsPage } from "./pages/ProjectsPage";
import { TestSuitesPage } from "./pages/TestSuitesPage";
import { RunHistoryPage } from "./pages/RunHistoryPage";
import { NewTestPage } from "./pages/NewTestPage";
import { ScanPage } from "./pages/ScanPage";
import { ScanResultsPage } from "./pages/ScanResultsPage";
import { VulnerabilitiesPage } from "./pages/VulnerabilitiesPage";
import { QAGapsPage } from "./pages/QAGapsPage";
import { TestCasesPage } from "./pages/TestCasesPage";
import { ReportsPage } from "./pages/ReportsPage";
import { NewScanPage } from "./pages/NewScanPage";
import { ChooseTestsPage } from "./pages/ChooseTestsPage";
import { ScanDetailPage } from "./pages/ScanDetailPage";
import { ScansListPage } from "./pages/ScansListPage";
import { AdminPage } from "./pages/AdminPage";
import { LoadingSpinner } from "./components/LoadingSpinner";
import { useMe } from "./hooks/useMe";

function RequireAuth({ children }: { children: JSX.Element }) {
  const token = localStorage.getItem("token");
  return token ? children : <Navigate to="/login" replace />;
}

/** Only super admins get in; everyone else goes back to their own overview. The API enforces this too. */
function RequireSuperAdmin({ children }: { children: JSX.Element }) {
  const me = useMe();
  if (!me) return <LoadingSpinner />;
  return me.role === "super_admin" ? children : <Navigate to="/" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<RequireAuth><Dashboard /></RequireAuth>} />
        <Route path="/projects/new" element={<RequireAuth><ProjectsPage /></RequireAuth>} />
        <Route path="/projects/:projectId/suites" element={<RequireAuth><TestSuitesPage /></RequireAuth>} />
        <Route path="/projects/:projectId/suites/new" element={<RequireAuth><NewTestPage /></RequireAuth>} />
        <Route path="/projects/:projectId/suites/:suiteId/runs" element={<RequireAuth><RunHistoryPage /></RequireAuth>} />
        <Route path="/scans/new" element={<RequireAuth><NewScanPage /></RequireAuth>} />
        <Route path="/scans/quick" element={<RequireAuth><ScanPage /></RequireAuth>} />
        <Route path="/scans/:id" element={<RequireAuth><ScanResultsPage /></RequireAuth>} />
        <Route path="/scans/:id/vulnerabilities" element={<RequireAuth><VulnerabilitiesPage /></RequireAuth>} />
        <Route path="/scans/:id/gaps" element={<RequireAuth><QAGapsPage /></RequireAuth>} />
        <Route path="/scans/:id/test-cases" element={<RequireAuth><TestCasesPage /></RequireAuth>} />
        <Route path="/scans/:id/reports" element={<RequireAuth><ReportsPage /></RequireAuth>} />
        <Route path="/admin" element={<RequireAuth><RequireSuperAdmin><AdminPage /></RequireSuperAdmin></RequireAuth>} />
        <Route path="/audits" element={<RequireAuth><ScansListPage /></RequireAuth>} />
        <Route path="/audits/new" element={<Navigate to="/scans/new" replace />} />
        <Route path="/audits/:id/setup" element={<RequireAuth><ChooseTestsPage /></RequireAuth>} />
        <Route path="/audits/:id" element={<RequireAuth><ScanDetailPage /></RequireAuth>} />
      </Routes>
    </BrowserRouter>
  );
}
