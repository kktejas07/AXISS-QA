export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  role: UserRole;
  organization_id: string | null;
  org_role: OrgRole;
}

export type OrgRole = "owner" | "admin" | "member" | "viewer";
export type AccountType = "individual" | "team" | "enterprise";
/** What a role allows. Viewers have none of these. */
export type Permission = "scan.run" | "members.manage" | "org.edit";

/** The signed-in user with their organisation and what their role allows. */
export interface Me extends User {
  organization: { id: string; name: string; account_type: AccountType; status: "active" | "suspended" };
  permissions: Permission[];
}

export interface Org {
  id: string;
  name: string;
  account_type: AccountType;
  status: "active" | "suspended";
  seat_limit: number | null;
  scan_limit: number | null;
  seats_used: number;
  pending_invites: number;
  scans_this_month: number;
  my_role: OrgRole;
  permissions: Permission[];
}

export interface Member {
  id: string;
  full_name: string;
  email: string;
  org_role: OrgRole;
  is_active: boolean;
  created_at: string;
}

export interface Invite {
  id: string;
  email: string;
  role: OrgRole;
  token: string;
  created_at: string;
  /** Only on the answer to creating an invite: true when the link was emailed. */
  emailed?: boolean;
}

export interface AdminOrg {
  id: string;
  name: string;
  account_type: AccountType;
  status: "active" | "suspended";
  seat_limit: number | null;
  scan_limit: number | null;
  member_count: number;
  scans_this_month: number;
  owner_email: string | null;
  created_at: string;
  members?: { id: string; full_name: string; email: string; org_role: OrgRole; is_active: boolean }[];
}

export interface AuditLogEntry {
  id: string;
  actor_email: string;
  action: string;
  target: string;
  detail: string;
  created_at: string;
}

export type UserRole = "user" | "super_admin";

export interface DashboardSummary {
  projects: number;
  scans: number;
  open_vulnerabilities: Record<Severity, number>;
  qa_gaps: number;
  test_cases: Record<string, number>;
  recent_scans: {
    id: string;
    /** "audit" opens /audits/:id (main flow); "scan" opens /scans/:id (quick security scan). */
    kind: "audit" | "scan";
    url: string;
    status: string;
    progress: number;
    created_at: string;
    critical: number;
    high: number;
    total: number;
  }[];
  top_findings: { id: string; scan_id: string; kind: "audit" | "scan"; severity: Severity; title: string; affected_url: string }[];
}

export interface AdminOverview {
  users_total: number;
  users_active: number;
  super_admins: number;
  projects_total: number;
  scans_total: number;
  scans_today: number;
  scans_running: number;
  scans_queued: number;
  scans_failed_today: number;
  open_vulnerabilities: Record<Severity, number>;
}

export interface AdminUser {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  role: UserRole;
  created_at: string;
  project_count: number;
  scan_count: number;
  organization_name: string | null;
  org_role: OrgRole | null;
}

export interface AdminScan {
  id: string;
  url: string;
  status: string;
  progress: number;
  created_at: string;
  owner_email: string;
}

export interface Project {
  id: string;
  name: string;
  description?: string;
  base_url: string;
  owner_id: string;
  created_at: string;
}

export interface Suite {
  id: string;
  name: string;
  description?: string;
  feature_description: string;
  generated_code?: string;
  status: "draft" | "active" | "archived";
  project_id: string;
  created_at: string;
}

export type RunStatus = "queued" | "running" | "passed" | "failed" | "error";

export interface Run {
  id: string;
  suite_id: string;
  status: RunStatus;
  triggered_by: string;
  branch?: string;
  commit_sha?: string;
  duration_ms?: number;
  tests_total?: number;
  tests_passed?: number;
  tests_failed?: number;
  error_message?: string;
  triage_summary?: string;
  screenshot_urls?: string;
  started_at?: string;
  finished_at?: string;
  created_at: string;
}

export type ScanType = "passive" | "active" | "hybrid";
export type ScanProfile = "owasp_top10" | "pci_dss" | "hipaa" | "custom";
export type ScanStatus = "queued" | "crawling" | "scanning" | "analyzing" | "completed" | "failed";
export type Severity = "critical" | "high" | "medium" | "low" | "informational";
export type CoverageStatus = "covered" | "partial" | "uncovered";
export type TestCaseType = "manual" | "unit" | "smoke" | "regression" | "integration" | "performance" | "accessibility" | "security";
export type ReportType = "executive_summary" | "vulnerability" | "qa_gap" | "compliance";
export type ReportFormat = "pdf" | "json" | "csv";

export interface AuthConfig {
  type: "none" | "cookie" | "bearer" | "oauth" | "basic";
  value?: string;
  username?: string;
  password?: string;
}

export interface ScanConfig {
  url: string;
  scan_type: ScanType;
  profile: ScanProfile;
  auth: AuthConfig;
  include_paths: string[];
  exclude_paths: string[];
  crawl_depth: number;
  rate_limit: number;
}

export interface Scan {
  id: string;
  project_id?: string;
  url: string;
  scan_type: ScanType;
  profile: ScanProfile;
  status: ScanStatus;
  progress: number;
  risk_grade: string;
  vulnerability_count: { critical: number; high: number; medium: number; low: number; informational: number };
  coverage_percent: number;
  test_cases_generated: number;
  routes_discovered: number;
  started_at?: string;
  completed_at?: string;
  created_at: string;
}

export interface Vulnerability {
  id: string;
  scan_id: string;
  severity: Severity;
  title: string;
  description: string;
  affected_url: string;
  affected_parameter?: string;
  owasp_category: string;
  cwe_id?: string;
  cve_id?: string;
  cvss_score?: number;
  proof_request?: string;
  proof_response?: string;
  remediation: string;
  fix_effort: string;
  status: "open" | "fixed" | "accepted" | "false-positive";
}

export interface QAGap {
  id: string;
  scan_id: string;
  route: string;
  coverage_status: CoverageStatus;
  risk_level: Severity;
  gap_type: string;
  description: string;
  recommendation: string;
}

export interface TestCase {
  id: string;
  scan_id: string;
  title: string;
  test_type: TestCaseType;
  language: string;
  priority: Severity;
  steps?: string;
  code?: string;
  preconditions?: string;
  expected_result?: string;
}

export interface Report {
  id: string;
  scan_id: string;
  report_type: ReportType;
  format: ReportFormat;
  status: "generating" | "ready" | "failed";
  download_url?: string;
  created_at: string;
}
