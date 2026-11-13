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
