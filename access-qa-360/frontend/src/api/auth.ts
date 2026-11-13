import api from "./client";
import type { Me, User } from "../types";

export const login = (email: string, password: string) =>
  api.post<{ access_token: string }>("/auth/login", { email, password });

/** With an invite token the new account joins that organisation; without one it gets its own. */
export const register = (email: string, password: string, full_name: string, invite_token?: string) =>
  api.post<User>("/auth/register", { email, password, full_name, invite_token });

export const getMe = () => api.get<Me>("/auth/me");

export const previewInvite = (token: string) =>
  api.get<{ organization_name: string; email: string; role: string }>(`/invites/${token}`);

/** Always succeeds; "admin" means this server sends no email and an administrator must make the link. */
export const forgotPassword = (email: string) => api.post<{ delivery: "email" | "admin" }>("/auth/forgot-password", { email });

export const checkResetLink = (token: string) => api.get<{ email: string }>(`/auth/reset-password/${encodeURIComponent(token)}`);

export const resetPassword = (token: string, password: string) => api.post<{ email: string }>("/auth/reset-password", { token, password });

/** Signs out other devices and returns a fresh token for this one. */
export const changePassword = (current_password: string, new_password: string) =>
  api.post<{ access_token: string }>("/auth/change-password", { current_password, new_password });
