import api from "./client";
import type { Suite } from "../types";

export const getSuites = (projectId: string) =>
  api.get<Suite[]>(`/projects/${projectId}/suites`);

export const createSuite = (projectId: string, data: { name: string; feature_description: string; description?: string }) =>
  api.post<Suite>(`/projects/${projectId}/suites`, data);
