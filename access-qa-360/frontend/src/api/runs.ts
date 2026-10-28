import api from "./client";
import type { Run } from "../types";

export const getRuns = (projectId: string, suiteId: string) =>
  api.get<Run[]>(`/projects/${projectId}/suites/${suiteId}/runs`);

export const triggerRun = (projectId: string, suiteId: string) =>
  api.post<Run>(`/projects/${projectId}/suites/${suiteId}/runs`, { triggered_by: "manual" });
