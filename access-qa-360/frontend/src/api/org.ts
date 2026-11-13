import api from "./client";
import type { Invite, Member, Org, OrgRole } from "../types";

export const getOrg = () => api.get<Org>("/org");

export const renameOrg = (name: string) => api.patch<Org>("/org", { name });

export const getMembers = () => api.get<Member[]>("/org/members");

export const changeRole = (userId: string, role: OrgRole) => api.patch<Member>(`/org/members/${userId}`, { role });

export const removeMember = (userId: string) => api.delete(`/org/members/${userId}`);

export const getInvites = () => api.get<Invite[]>("/org/invites");

export const createInvite = (email: string, role: OrgRole) => api.post<Invite>("/org/invites", { email, role });

export const cancelInvite = (id: string) => api.delete(`/org/invites/${id}`);
