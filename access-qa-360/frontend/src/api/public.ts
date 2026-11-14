import api from "./client";

export interface ContactForm { name: string; email: string; company?: string; kind: "demo" | "pricing" | "enterprise" | "other"; message: string; website?: string }
export interface ContactRequest { id: string; name: string; email: string; company: string | null; kind: string; about: string; message: string; created_at: string; handled_at: string | null }
export interface ServiceStatus { ok: boolean; checked_at: string; parts: { name: string; ok: boolean }[] }

export const sendContact = (form: ContactForm) => api.post<{ received: boolean }>("/public/contact", form);
export const getStatus = () => api.get<ServiceStatus>("/status", { timeout: 10000 });
export const getContacts = () => api.get<ContactRequest[]>("/admin/contacts");
export const markContact = (id: string, handled: boolean) => api.put<ContactRequest>(`/admin/contacts/${id}`, { handled });
