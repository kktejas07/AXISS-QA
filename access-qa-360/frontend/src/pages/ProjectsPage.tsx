import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Layout } from "../components/Layout";
import { createProject } from "../api/projects";
import { FolderPlus } from "lucide-react";

export function ProjectsPage() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await createProject({ name, base_url: baseUrl, description: description || undefined });
      navigate("/");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Layout>
      <div className="mb-6 flex items-center gap-2">
        <FolderPlus className="w-5 h-5 text-accent" />
        <h1 className="text-2xl font-semibold text-fg">New Project</h1>
      </div>

      <div className="bg-surface-1 border border-surface-3 rounded-card p-6 max-w-xl">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="refero-label">Project name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              placeholder="e.g. My Web App"
              className="refero-input"
            />
          </div>
          <div>
            <label className="refero-label">Base URL</label>
            <input
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              required
              placeholder="https://your-app.com"
              className="refero-input"
            />
          </div>
          <div>
            <label className="refero-label">Description (optional)</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="Brief description of your project"
              className="refero-input resize-none"
            />
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="refero-btn-primary w-full py-2.5"
          >
            {submitting ? "Creating…" : "Create Project"}
          </button>
        </form>
      </div>
    </Layout>
  );
}
