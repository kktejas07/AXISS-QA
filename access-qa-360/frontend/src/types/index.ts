export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
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
export type ScanProfile = "owasp-top-10" | "pci-dss" | "hipaa" | "custom";
export type ScanStatus = "queued" | "crawling" | "scanning" | "analyzing" | "completed" | "failed";
export type Severity = "critical" | "high" | "medium" | "low" | "informational";
export type CoverageStatus = "covered" | "partial" | "uncovered";
export type TestCaseType = "manual" | "unit" | "smoke" | "regression" | "integration" | "performance" | "accessibility" | "security";
export type ReportType = "executive" | "vulnerability" | "qa-gap" | "test-bundle" | "compliance" | "diff";
export type ReportFormat = "pdf" | "json" | "docx" | "csv" | "feature" | "py" | "ts";

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
