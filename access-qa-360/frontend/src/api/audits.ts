import api from "./client";

export type SourceType = "web" | "android" | "ios" | "code" | "repo";

export const sourceName: Record<SourceType, string> = {
  web: "Web app",
  android: "Android build",
  ios: "iOS build",
  code: "Source code",
  repo: "Repository",
};
export const isCode = (job: { source_type: SourceType }) => job.source_type === "code" || job.source_type === "repo";
export type OutputKind = "security" | "manual" | "playwright" | "appium";
export type Depth = "quick" | "standard" | "deep";
export type ExportKind = "report" | "test-cases" | "playwright" | "appium" | "results";
export type AuditStatus = "queued" | "running" | "completed" | "failed" | "partial";
export type StepStatus = "pending" | "running" | "completed" | "failed" | "skipped";

export interface Finding {
  id?: string;
  /** Code scans: "secrets", "code", "config" or "dependency". */
  check?: string;
  severity: string;
  title: string;
  description?: string;
  detail?: string;
  affected_url?: string;
  method?: string;
  proof_request?: string;
  proof_response?: string;
  cwe_id?: string;
  owasp_category?: string;
  remediation?: string;
}

export interface ManualCase {
  id?: string;
  title: string;
  category?: string;
  priority?: string;
  preconditions?: string;
  steps?: string[];
  expected_result?: string;
  page_url?: string;
}

export interface A11yViolation {
  id: string;
  impact: string;
  description: string;
  help: string;
  helpUrl: string;
  occurrences: number;
  affected_pages: string[];
}

export interface WebResult {
  error?: string;
  skipped?: string;
  pages_audited?: number;
  routes_found?: string[];
  playwright_tests?: string;
  a11y_summary?: { total_violations: number; critical: number; serious: number; moderate: number; minor: number; violations: A11yViolation[] };
  // Source code scans
  files_scanned?: number;
  truncated?: boolean;
  languages?: Record<string, number>;
  routes?: CodeRoute[];
  qa_gaps?: QaGaps;
}

export interface CodeRoute {
  method: string;
  path: string;
  file: string;
  line: number;
  tested?: boolean;
}

export interface QaGaps {
  source_files: number;
  test_files: number;
  files_with_tests: number;
  coverage_pct: number | null;
  untested_files: { path: string; lines: number; language: string }[];
  untested_file_count: number;
  untested_routes: CodeRoute[];
  untested_route_count: number;
  route_count: number;
}

export interface MobileResult {
  error?: string;
  skipped?: string;
  platform?: string;
  app_name?: string;
  app_id?: string;
  version?: string;
  permissions?: string[];
  dangerous_permissions?: string[];
  security_flags?: Finding[];
  appium_tests?: string;
}

export interface SecurityResult {
  error?: string;
  skipped?: string;
  findings?: Finding[];
  subdomains_found?: string[];
  /** Code scans: what the dependency lookup covered. */
  dependencies?: { packages_found: number; packages_checked: number; vulnerable: number; status: "none" | "checked" | "unavailable"; reason?: string };
}

export interface ManualResult {
  error?: string;
  skipped?: string;
  note?: string;
  test_cases?: ManualCase[];
}

export interface AuditJob {
  id: string;
  label: string;
  source_type: SourceType;
  target_url: string | null;
  app_name: string | null;
  mobile_url: string | null;
  repo_url: string | null;
  source_filename: string | null;
  outputs: OutputKind[] | null;
  allowed_outputs: OutputKind[];
  depth: Depth;
  status: AuditStatus;
  progress: number;
  tier1_status: StepStatus;
  tier2_status: StepStatus;
  tier3_status: StepStatus;
  tier4_status: StepStatus;
  tier5_status: StepStatus;
  risk_score: number | null;
  critical_count: number;
  high_count: number;
  total_test_cases: number;
  total_pages_audited: number;
  executive_summary: string | null;
  exports: ExportKind[];
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  // Results come with the single-scan request only.
  tier1_result?: WebResult | null;
  tier2_result?: MobileResult | null;
  tier3_result?: SecurityResult | null;
  tier4_result?: ManualResult | null;
  tier5_result?: { error?: string; skipped?: string } | null;
}

/** Step 1: record what is being tested. Nothing runs until startAudit. */
export const createDraft = (body: { source_type: SourceType; target_url?: string; repo_url?: string; app_name?: string }) =>
  api.post<AuditJob>("/audits", { ...body, autostart: false });

export const uploadBuild = (id: string, file: File, onProgress?: (percent: number) => void) => {
  const form = new FormData();
  form.append("file", file);
  return api.post<AuditJob>(`/audits/${id}/upload`, form, {
    onUploadProgress: (e) => e.total && onProgress?.(Math.round((e.loaded / e.total) * 100)),
  });
};

/** Step 2: choose outputs and depth, confirm permission, and run. */
export const startAudit = (id: string, body: { outputs: OutputKind[]; depth: Depth; ownership_confirmed: boolean }) =>
  api.post<AuditJob>(`/audits/${id}/start`, body);

export const listAudits = () => api.get<AuditJob[]>("/audits");

export const getAudit = (id: string) => api.get<AuditJob>(`/audits/${id}`);

export const exportPath = (id: string, kind: ExportKind) => `/audits/${id}/export/${kind}`;
