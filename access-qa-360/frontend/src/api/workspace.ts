import api from "./client";

export type FindingStatus = "open" | "fixed" | "accepted" | "false_positive";
export interface InboxItem {
  audit_id: string;
  app: string;
  source: "security" | "mobile" | "accessibility" | "performance";
  index: number;
  severity: string;
  title: string;
  location: string;
  status: FindingStatus;
  note: string | null;
  assignee_id: string | null;
  assignee: string | null;
  found_at: string;
}
export interface Inbox { counts: Record<FindingStatus, number>; total: number; items: InboxItem[] }

export const getInbox = (filters: { status?: string; severity?: string; assignee?: string }) =>
  api.get<Inbox>("/findings", { params: Object.fromEntries(Object.entries(filters).filter(([, v]) => v)) });
export const setFindingState = (body: { audit_id: string; source: string; index: number; status: FindingStatus; assignee_id?: string | null; note?: string | null }) =>
  api.put<{ status: FindingStatus }>("/findings/state", body);
export const sbomPath = (auditId: string) => `/audits/${auditId}/sbom.json`;

export interface Notice { id: string; at: string; text: string; path: string; tone: "ok" | "bad" }
export const getNotifications = () => api.get<Notice[]>("/notifications");

export interface FirstSteps { steps: { id: string; label: string; about: string; path: string; done: boolean }[]; done: number; total: number }
export const getFirstSteps = () => api.get<FirstSteps>("/onboarding");
