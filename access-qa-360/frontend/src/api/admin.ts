import api from "./client";
import type { AccountType, AdminOrg, AdminOverview, AdminScan, AdminUser, AuditLogEntry, UserRole } from "../types";

export const getAdminOverview = () => api.get<AdminOverview>("/admin/overview");

export const getAdminUsers = () => api.get<AdminUser[]>("/admin/users");

export const updateAdminUser = (id: string, changes: { role?: UserRole; is_active?: boolean }) =>
  api.patch<AdminUser>(`/admin/users/${id}`, changes);

export const getAdminScans = (limit = 20) => api.get<AdminScan[]>("/admin/scans", { params: { limit } });

export const getAdminOrgs = () => api.get<AdminOrg[]>("/admin/organizations");

export const getAdminOrg = (id: string) => api.get<AdminOrg>(`/admin/organizations/${id}`);

/** Send only what changes. A limit of null removes the limit. */
export const updateAdminOrg = (
  id: string,
  changes: { account_type?: AccountType; seat_limit?: number | null; scan_limit?: number | null; status?: "active" | "suspended" }
) => api.patch<AdminOrg>(`/admin/organizations/${id}`, changes);

export const getAuditLog = () => api.get<AuditLogEntry[]>("/admin/audit-log");

/** A single-use password reset link for a locked-out user. Shown once; pass it to them yourself. */
export const createResetLink = (userId: string) =>
  api.post<{ url: string; expires_at: string; email: string }>(`/admin/users/${userId}/reset-link`);

// ---- operations ------------------------------------------------------------

export interface QueueRow {
  id: string;
  label: string;
  source_type: string;
  status: string;
  progress: number;
  organization: string | null;
  started_by: string;
  started_at: string | null;
  completed_at: string | null;
  step: string | null;
  problem: string | null;
  /** False for a scan marked running that the server is no longer working on. */
  alive: boolean;
}

export interface UsageBucket {
  calls: number;
  failed: number;
  input_tokens: number;
  output_tokens: number;
  cost: number;
}

export interface AiUsage {
  days: number;
  total: UsageBucket;
  by_model: (UsageBucket & { model: string })[];
  by_organization: (UsageBucket & { organization: string })[];
  by_purpose: (UsageBucket & { purpose: string })[];
  by_day: (UsageBucket & { day: string })[];
  unpriced_models: string[];
  ai_configured: boolean;
}

export interface HealthCheck {
  name: string;
  status: "ok" | "down" | "off";
  detail: string;
  required: boolean;
}

export interface Health {
  healthy: boolean;
  checked_at: string;
  environment: string;
  scans_running_here: number;
  checks: HealthCheck[];
}

export const getQueue = () => api.get<{ active: QueueRow[]; failed_last_24h: QueueRow[]; completed_last_24h: number }>("/admin/queue");
export const adminStopScan = (id: string) => api.post(`/admin/audits/${id}/stop`);
export const getAiUsage = (days: number) => api.get<AiUsage>("/admin/ai-usage", { params: { days } });
export const getHealth = () => api.get<Health>("/admin/health");
