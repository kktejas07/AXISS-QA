import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { Layout } from "../components/Layout";
import { createSuite } from "../api/suites";
import { Sparkles } from "lucide-react";

export function NewTestPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectId) return;
    setSubmitting(true);
    try {
      await createSuite(projectId, { name, feature_description: description });
      navigate(`/projects/${projectId}/suites`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Layout>
      <Link
        to={`/projects/${projectId}/suites`}
        className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-accent transition-colors mb-5"
      >
        ← Back to Suites
      </Link>

      <h1 className="text-2xl font-semibold text-fg mt-1 mb-6">Generate Test Suite</h1>

      <div className="bg-surface-1 border border-surface-3 rounded-card p-6 max-w-2xl">
        {/* AI badge */}
        <div className="flex items-center gap-2 mb-5 px-3 py-2 bg-accent/10 border border-accent/30 rounded-badge w-fit">
          <Sparkles className="w-4 h-4 text-accent" />
          <span className="text-xs font-semibold text-accent">
            Claude Sonnet will generate Playwright tests from your description
          </span>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="refero-label">Suite name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              placeholder="e.g. User login flow"
              className="refero-input mt-1"
            />
          </div>

          <div>
            <label className="refero-label">Feature description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              required
              rows={5}
              placeholder="Describe what to test in plain English. E.g. 'Test that a user can log in with valid credentials, see their dashboard, and that invalid passwords show an error message.'"
              className="refero-input mt-1 resize-none"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="refero-btn-primary w-full py-2.5 flex items-center justify-center gap-2"
          >
            <Sparkles className="w-4 h-4" />
            {submitting ? "Sending to Claude…" : "Generate Tests with AI"}
          </button>
        </form>
      </div>
    </Layout>
  );
}
