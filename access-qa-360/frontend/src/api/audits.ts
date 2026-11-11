import api from "./client";

export interface AuditCreate {
  target_url: string;
  app_name?: string;
  mobile_url?: string;
}

export interface AuditJob {
  id: string;
  target_url: string;
  app_name: string | null;
  mobile_url: string | null;
  status: "queued" | "running" | "completed" | "failed" | "partial";
  progress: number;
  tier1_status: string;
  tier2_status: string;
  tier3_status: string;
  tier4_status: string;
  tier5_status: string;
  risk_score: number | null;
  coverage_pct: number | null;
  critical_count: number;
  high_count: number;
  total_test_cases: number;
  total_pages_audited: number;
  executive_summary: string | null;
  report_pdf_path: string | null;
  created_at: string;
  completed_at: string | null;
  // tier results only on detail endpoint
  tier1_result?: Record<string, unknown> | null;
  tier2_result?: Record<string, unknown> | null;
  tier3_result?: Record<string, unknown> | null;
  tier4_result?: Record<string, unknown> | null;
  tier5_result?: Record<string, unknown> | null;
}

export const createAudit = (body: AuditCreate) =>
  api.post<AuditJob>("/audits", body);

export const listAudits = () =>
  api.get<AuditJob[]>("/audits");

export const getAudit = (id: string) =>
  api.get<AuditJob>(`/audits/${id}`);

export const uploadApk = (id: string, file: File) => {
  const form = new FormData();
  form.append("file", file);
  return api.post<AuditJob>(`/audits/${id}/upload-apk`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};

export const uploadIpa = (id: string, file: File) => {
  const form = new FormData();
  form.append("file", file);
  return api.post<AuditJob>(`/audits/${id}/upload-ipa`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};
