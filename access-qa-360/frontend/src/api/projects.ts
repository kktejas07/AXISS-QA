import api from "./client";
import type { Project } from "../types";

export const getProjects = () => api.get<Project[]>("/projects");

export const createProject = (data: { name: string; base_url: string; description?: string }) =>
  api.post<Project>("/projects", data);

export const deleteProject = (id: string) => api.delete(`/projects/${id}`);
