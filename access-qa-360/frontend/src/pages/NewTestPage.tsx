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
      <Link to={`/projects/${projectId}/suites`} className="text-sm text-indigo-600 hover:underline">
        &larr; Back to Suites
      </Link>
      <h1 className="text-2xl font-bold text-brand-900 mt-2 mb-6">Generate Test Suite</h1>
      <div className="bg-white border border-gray-200 rounded-2xl p-6 max-w-2xl">
        <div className="flex items-center gap-2 mb-4 text-indigo-600">
          <Sparkles className="w-5 h-5" />
          <span className="text-sm font-semibold">
            Claude Sonnet will generate Playwright tests from your description
          </span>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Suite name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              placeholder="e.g. User login flow"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Feature description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              required
              rows={5}
              placeholder="Describe what to test in plain English. E.g. 'Test that a user can log in with valid credentials, see their dashboard, and that invalid passwords show an error message.'"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none resize-none"
            />
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-brand-600 hover:bg-brand-700 disabled:opacity-60 text-white font-semibold py-2 rounded-lg transition"
          >
            {submitting ? "Sending to Claude…" : "Generate Tests with AI"}
          </button>
        </form>
      </div>
    </Layout>
  );
}
