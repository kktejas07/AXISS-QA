import api from "./client";

export interface FlatFinding {
  source: "security" | "mobile" | "accessibility" | "performance";
  index: number;
  severity: string;
  title: string;
  description?: string;
  location: string;
  cwe_id?: string;
  fingerprint?: string;
}

export interface ScanBrief {
  id: string;
  label: string;
  created_at: string;
  risk_score: number | null;
  findings: number;
  counts: Record<string, number>;
  branch: string | null;
}

export interface Changes {
  scan: ScanBrief;
  /** The earlier scan this one is compared with; null when this is the first scan of its target. */
  baseline: ScanBrief | null;
  new: FlatFinding[];
  fixed: FlatFinding[];
  unchanged: number;
  history: ScanBrief[];
}

export interface Standards {
  standard: string;
  categories: { code: string; name: string; count: number; worst: string | null; findings: FlatFinding[] }[];
  other: FlatFinding[];
  accessibility: FlatFinding[];
  covered: number;
}

export const getChanges = (id: string, against?: string) => api.get<Changes>(`/audits/${id}/changes`, { params: against ? { against } : undefined });
export const getStandards = (id: string) => api.get<Standards>(`/audits/${id}/standards`);
export const standardsCsvPath = (id: string) => `/audits/${id}/standards.csv`;

// ---- schedules ---------------------------------------------------------------

export type Frequency = "daily" | "weekly" | "monthly";

export interface Schedule {
  id: string;
  source_type: "web" | "repo";
  target: string;
  frequency: Frequency;
  outputs: string[];
  depth: string;
  active: boolean;
  next_run_at: string;
  last_run_at: string | null;
  last_audit_id: string | null;
  last_note: string | null;
}

export const getSchedules = () => api.get<Schedule[]>("/schedules");
export const createSchedule = (body: { source_type: "web" | "repo"; target: string; frequency: Frequency; outputs: string[]; depth: string; ownership_confirmed: boolean }) =>
  api.post<Schedule>("/schedules", body);
export const changeSchedule = (id: string, body: { frequency?: Frequency; active?: boolean }) => api.patch<Schedule>(`/schedules/${id}`, body);
export const deleteSchedule = (id: string) => api.delete(`/schedules/${id}`);
export const runScheduleNow = (id: string) => api.post<Schedule>(`/schedules/${id}/run`);

// ---- connections -------------------------------------------------------------

export interface Connections {
  slack: { connected: boolean; events?: "automatic" | "all" };
  teams: { connected: boolean; events?: "automatic" | "all" };
  github: { connected: boolean; login?: string; repo?: string | null; fail_on?: "critical" | "high" | "never"; webhook_url?: string; webhook_secret?: string };
  linear: { connected: boolean; team_key?: string; team_name?: string };
}
export type ConnectionKind = keyof Connections;

export const getConnections = () => api.get<Connections>("/org/connections");
export const saveChat = (kind: "slack" | "teams", body: { webhook_url: string; events: "automatic" | "all" }) => api.put<Connections["slack"]>(`/org/connections/${kind}`, body);
export const saveGitHub = (body: { token: string; repo?: string; fail_on: string }) => api.put<Connections["github"]>("/org/github", body);
export const saveLinear = (body: { api_key: string; team_key: string }) => api.put<Connections["linear"]>("/org/linear", body);
export const disconnect = (kind: ConnectionKind) => api.delete(`/org/connections/${kind}`);
