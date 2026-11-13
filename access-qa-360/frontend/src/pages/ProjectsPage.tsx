import { FolderStack } from "../components/Illustrations";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Plus } from "lucide-react";
import { Layout } from "../components/Layout";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { createProject, getProjects } from "../api/projects";
import { useCan } from "../hooks/useMe";
import type { Project } from "../types";
import { apiError } from "../utils/errors";
import { backLink, card, emptyState, errorBox, field, hint, label, pageTitle, primaryButton, textarea } from "../components/ui";

/** Every project, each leading to its generated test suites. */
export function ProjectsListPage() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [failed, setFailed] = useState(false);
  const canCreate = useCan("scan.run");

  useEffect(() => {
    getProjects()
      .then((r) => setProjects(r.data))
      .catch(() => setFailed(true));
  }, []);

  return (
    <Layout>
      <div className="mb-7 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className={pageTitle}>Projects</h1>
          <p className="mt-1 text-body">A project groups the test suites you generate for one app.</p>
        </div>
        {canCreate && (
          <Link to="/projects/new" className={primaryButton}>
            <Plus className="h-[18px] w-[18px]" strokeWidth={2.4} aria-hidden="true" /> New project
          </Link>
        )}
      </div>
      {failed ? (
        <p role="alert" className={errorBox}>Your projects could not be loaded. Check that the API is running, then reload the page.</p>
      ) : !projects ? (
        <LoadingSpinner />
      ) : projects.length === 0 ? (
        <div className={emptyState}>
          <FolderStack className="mx-auto mb-4 h-36 w-auto" />
          <p>No projects yet. Create one to start generating Playwright test suites from plain descriptions.</p>
        </div>
      ) : (
        <ul className={`${card} overflow-hidden`}>
          {projects.map((p, i) => (
            <li key={p.id} className={`flex flex-wrap items-center justify-between gap-x-6 gap-y-2 px-5 py-4 ${i ? "border-t border-line" : ""}`}>
              <div className="min-w-0">
                <Link to={`/projects/${p.id}/suites`} className="font-bold text-brand-600 hover:text-brand-700">{p.name}</Link>
                <div className="break-all font-mono text-[13px] text-body">{p.base_url}</div>
                {p.description && <p className="mt-1 text-[14.5px] text-body">{p.description}</p>}
              </div>
              <span className="whitespace-nowrap text-[13.5px] text-body">Created {new Date(p.created_at).toLocaleDateString()}</span>
            </li>
          ))}
        </ul>
      )}
    </Layout>
  );
}

export function ProjectsPage() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const { data } = await createProject({ name: name.trim(), base_url: baseUrl.trim(), description: description.trim() || undefined });
      navigate(`/projects/${data.id}/suites`);
    } catch (err) {
      setError(apiError(err, "Could not create the project. Try again."));
      setSubmitting(false);
    }
  };

  return (
    <Layout>
      <Link to="/projects" className={backLink}>Projects</Link>
      <h1 className={`${pageTitle} mb-7 mt-1`}>New project</h1>
      <form onSubmit={handleSubmit} className={`${card} flex max-w-2xl flex-col gap-5 p-7`}>
        <label className={label}>
          Project name
          <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} placeholder="Customer web app" className={field} />
        </label>
        <label className={label}>
          Web address
          <input type="url" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} required placeholder="https://your-app.com" className={`${field} font-mono`} />
          <span className={hint}>Generated tests open this address.</span>
        </label>
        <label className={label}>
          Description <span className="sr-only">(optional)</span>
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} placeholder="Optional" className={`${textarea} resize-none`} />
        </label>
        {error && <p role="alert" className={errorBox}>{error}</p>}
        <button type="submit" disabled={submitting} className={`${primaryButton} self-start`}>
          {submitting ? "Creating" : "Create project"}
        </button>
      </form>
    </Layout>
  );
}
