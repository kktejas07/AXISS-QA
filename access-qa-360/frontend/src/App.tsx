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

function RequireAuth({ children }: { children: JSX.Element }) {
  const token = localStorage.getItem("token");
  return token ? children : <Navigate to="/login" replace />;
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
        <Route path="/scans/new" element={<RequireAuth><ScanPage /></RequireAuth>} />
        <Route path="/scans/:id" element={<RequireAuth><ScanResultsPage /></RequireAuth>} />
        <Route path="/scans/:id/vulnerabilities" element={<RequireAuth><VulnerabilitiesPage /></RequireAuth>} />
        <Route path="/scans/:id/gaps" element={<RequireAuth><QAGapsPage /></RequireAuth>} />
        <Route path="/scans/:id/test-cases" element={<RequireAuth><TestCasesPage /></RequireAuth>} />
        <Route path="/scans/:id/reports" element={<RequireAuth><ReportsPage /></RequireAuth>} />
      </Routes>
    </BrowserRouter>
  );
}
