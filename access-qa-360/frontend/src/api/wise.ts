import api from "./client";

export interface WiseSource { title: string; link: string; kind: string }
export interface WiseAction { label: string; path: string }
export interface WiseReply { answer: string; sources: WiseSource[]; actions: WiseAction[]; used_ai: boolean }
export interface WiseMessage { role: "user" | "assistant"; content: string; sources?: WiseSource[]; actions?: WiseAction[] }
export interface WisePrompt { id: string; label: string; text: string }
export interface WiseDocument { id: string; name: string; size: number; created_at: string }

export const askWise = (messages: WiseMessage[], auditId?: string) =>
  api.post<WiseReply>("/wise/chat", { messages: messages.slice(-12).map(({ role, content }) => ({ role, content: content.slice(0, 4000) })), audit_id: auditId });
export const getWisePrompts = () => api.get<WisePrompt[]>("/wise/prompts");
export const getWiseDocuments = () => api.get<WiseDocument[]>("/wise/documents");
export const addWiseDocument = (file: File) => {
  const form = new FormData();
  form.append("file", file);
  return api.post<WiseDocument>("/wise/documents", form);
};
export const removeWiseDocument = (id: string) => api.delete(`/wise/documents/${id}`);

export interface ScanPreset { id: string; name: string; about: string; outputs: string[]; depth: "quick" | "standard" | "deep"; for: string[] }
export interface TestPack { id: string; name: string; about: string; cases: { id: string; title: string; steps: string[]; expected_result: string; priority: string; category: string }[] }
export const getLibrary = () => api.get<{ scan_presets: ScanPreset[]; test_packs: TestPack[] }>("/library");
export const packCsvPath = (id: string) => `/library/test-packs/${id}.csv`;

export interface FlowNode { id: number; path: string; url: string; title: string; status: number | null; depth: number; forms: number; form_fields: string[]; api_calls: string[]; a11y: number; lcp_ms: number | null }
export interface Flows { nodes: FlowNode[]; edges: { from: number; to: number }[]; pages_crawled: number; shown: number }
export const getFlows = (auditId: string) => api.get<Flows>(`/audits/${auditId}/flows`);
