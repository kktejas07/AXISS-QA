import api from "./client";
import type { User } from "../types";

export const login = (email: string, password: string) =>
  api.post<{ access_token: string }>("/auth/login", { email, password });

export const register = (email: string, password: string, full_name: string) =>
  api.post<User>("/auth/register", { email, password, full_name });

export const getMe = () => api.get<User>("/auth/me");
