import api from "./client";

export interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  created_by_email: string | null;
  created_at: string;
  last_used_at: string | null;
  /** Only on the answer to creating a key. */
  key: string | null;
}

export interface JiraConnection {
  connected: boolean;
  base_url: string | null;
  email: string | null;
  project_key: string | null;
  project_name: string | null;
  issue_type: string | null;
}

export interface TrackerIssue {
  /** "security:3" or "mobile:0": which list the finding is in and its position there. */
  finding_ref: string;
  issue_key: string;
  issue_url: string;
}

export const getApiKeys = () => api.get<ApiKey[]>("/org/api-keys");
export const createApiKey = (name: string) => api.post<ApiKey>("/org/api-keys", { name });
export const revokeApiKey = (id: string) => api.delete(`/org/api-keys/${id}`);

export const getJira = () => api.get<JiraConnection>("/org/integrations/jira");
export const saveJira = (body: { base_url: string; email: string; api_token: string; project_key: string; issue_type: string }) =>
  api.put<JiraConnection>("/org/integrations/jira", body);
export const disconnectJira = () => api.delete("/org/integrations/jira");

export const getIssues = (auditId: string) => api.get<TrackerIssue[]>(`/audits/${auditId}/issues`);
export const createIssue = (auditId: string, source: "security" | "mobile", index: number) =>
  api.post<TrackerIssue>(`/audits/${auditId}/issues`, { source, index });
