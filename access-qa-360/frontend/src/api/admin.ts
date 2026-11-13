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
