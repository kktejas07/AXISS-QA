import api from "./client";
import type { AdminOverview, AdminScan, AdminUser, UserRole } from "../types";

export const getAdminOverview = () => api.get<AdminOverview>("/admin/overview");

export const getAdminUsers = () => api.get<AdminUser[]>("/admin/users");

export const updateAdminUser = (id: string, changes: { role?: UserRole; is_active?: boolean }) =>
  api.patch<AdminUser>(`/admin/users/${id}`, changes);

export const getAdminScans = (limit = 20) => api.get<AdminScan[]>("/admin/scans", { params: { limit } });
