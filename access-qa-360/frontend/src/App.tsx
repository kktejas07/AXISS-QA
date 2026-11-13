import { AdminKeysPage } from "./pages/AdminKeysPage";
import { HelpPage } from "./pages/HelpPage";
import { ProfilePage } from "./pages/ProfilePage";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { LoginPage } from "./pages/LoginPage";
import { Dashboard } from "./pages/Dashboard";
import { ProjectsListPage, ProjectsPage } from "./pages/ProjectsPage";
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
import { RegisterPage } from "./pages/RegisterPage";
import { PricingPage } from "./pages/PricingPage";
import { SsoPage } from "./pages/SsoPage";
import { AdminAiUsagePage, AdminHealthPage, AdminQueuePage } from "./pages/AdminOpsPages";
import { ForgotPasswordPage, ResetPasswordPage } from "./pages/PasswordPages";
import { SettingsPage } from "./pages/SettingsPage";
import { SchedulesPage } from "./pages/SchedulesPage";
import { LibraryPage } from "./pages/LibraryPage";
import { FindingsPage } from "./pages/FindingsPage";
import { LandingPage } from "./pages/LandingPage";
import { LegalPage } from "./pages/LegalPage";
import { AdminAuditPage, AdminOrgDetailPage, AdminOrgsPage } from "./pages/AdminOrgsPage";
import { AdminPage } from "./pages/AdminPage";
import { LoadingSpinner } from "./components/LoadingSpinner";
import { useMe } from "./hooks/useMe";

function RequireAuth({ children }: { children: JSX.Element }) {
  const token = localStorage.getItem("token");
  return token ? children : <Navigate to="/login" replace />;
}

/** Signed in: the overview. Signed out: the public page. Decided each time the page is shown, so signing in or out switches it. */
function Home() {
  return localStorage.getItem("token") ? <Dashboard /> : <LandingPage />;
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
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/pricing" element={<PricingPage />} />
        <Route path="/sso" element={<SsoPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/settings" element={<RequireAuth><SettingsPage /></RequireAuth>} />
        {/* Signed in: the overview. Signed out: the public page that says what Wiseflow is. */}
        <Route path="/" element={<Home />} />
        <Route path="/privacy" element={<LegalPage kind="privacy" />} />
        <Route path="/terms" element={<LegalPage kind="terms" />} />
        <Route path="/findings" element={<RequireAuth><FindingsPage /></RequireAuth>} />
        <Route path="/projects" element={<RequireAuth><ProjectsListPage /></RequireAuth>} />
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
        <Route path="/admin/organizations" element={<RequireAuth><RequireSuperAdmin><AdminOrgsPage /></RequireSuperAdmin></RequireAuth>} />
        <Route path="/admin/organizations/:id" element={<RequireAuth><RequireSuperAdmin><AdminOrgDetailPage /></RequireSuperAdmin></RequireAuth>} />
        <Route path="/admin/queue" element={<RequireAuth><RequireSuperAdmin><AdminQueuePage /></RequireSuperAdmin></RequireAuth>} />
        <Route path="/admin/ai-usage" element={<RequireAuth><RequireSuperAdmin><AdminAiUsagePage /></RequireSuperAdmin></RequireAuth>} />
        <Route path="/profile" element={<RequireAuth><ProfilePage /></RequireAuth>} />
        <Route path="/help" element={<RequireAuth><HelpPage /></RequireAuth>} />
        <Route path="/admin/keys" element={<RequireAuth><RequireSuperAdmin><AdminKeysPage /></RequireSuperAdmin></RequireAuth>} />
        <Route path="/admin/health" element={<RequireAuth><RequireSuperAdmin><AdminHealthPage /></RequireSuperAdmin></RequireAuth>} />
        <Route path="/admin/audit-log" element={<RequireAuth><RequireSuperAdmin><AdminAuditPage /></RequireSuperAdmin></RequireAuth>} />
        <Route path="/library" element={<RequireAuth><LibraryPage /></RequireAuth>} />
        <Route path="/schedules" element={<RequireAuth><SchedulesPage /></RequireAuth>} />
        <Route path="/audits" element={<RequireAuth><ScansListPage /></RequireAuth>} />
        <Route path="/audits/new" element={<Navigate to="/scans/new" replace />} />
        <Route path="/audits/:id/setup" element={<RequireAuth><ChooseTestsPage /></RequireAuth>} />
        <Route path="/audits/:id" element={<RequireAuth><ScanDetailPage /></RequireAuth>} />
      </Routes>
    </BrowserRouter>
  );
}
