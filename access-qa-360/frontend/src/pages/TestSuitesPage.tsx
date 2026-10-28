import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Layout } from "../components/Layout";
import { getSuites } from "../api/suites";
import type { Suite } from "../types";
import { Plus, CheckCircle, Clock, Code } from "lucide-react";

const statusIcon = (status: Suite["status"]) => {
  if (status === "active") return <CheckCircle className="w-4 h-4 text-emerald-500" />;
  if (status === "draft") return <Clock className="w-4 h-4 text-amber-500" />;
  return <Code className="w-4 h-4 text-gray-400" />;
};

export function TestSuitesPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [suites, setSuites] = useState<Suite[]>([]);

  useEffect(() => {
    if (projectId) getSuites(projectId).then((r) => setSuites(r.data));
  }, [projectId]);

  return (
    <Layout>
      <div className="flex items-center justify-between mb-6">
        <div>
          <Link to="/" className="text-sm text-indigo-600 hover:underline">
            &larr; Projects
          </Link>
          <h1 className="text-2xl font-bold text-brand-900 mt-1">Test Suites</h1>
        </div>
        <Link
          to={`/projects/${projectId}/suites/new`}
          className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white text-sm font-semibold px-4 py-2 rounded-lg transition"
        >
          <Plus className="w-4 h-4" /> Generate Tests
        </Link>
      </div>
      <div className="space-y-3">
        {suites.map((s) => (
          <div
            key={s.id}
            className="bg-white border border-gray-200 rounded-xl p-4 flex items-center justify-between"
          >
            <div className="flex items-center gap-3">
              {statusIcon(s.status)}
              <div>
                <p className="font-medium text-brand-900">{s.name}</p>
                <p className="text-xs text-gray-500 mt-0.5 line-clamp-1">{s.feature_description}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span
                className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                  s.status === "active"
                    ? "bg-emerald-100 text-emerald-700"
                    : "bg-amber-100 text-amber-700"
                }`}
              >
                {s.status}
              </span>
              {s.status === "active" && (
                <Link
                  to={`/projects/${projectId}/suites/${s.id}/runs`}
                  className="text-sm text-indigo-600 hover:underline font-medium"
                >
                  Run history &rarr;
                </Link>
              )}
            </div>
          </div>
        ))}
        {suites.length === 0 && (
          <p className="text-center text-gray-400 py-12">
            No test suites yet. Click "Generate Tests" to create your first one.
          </p>
        )}
      </div>
    </Layout>
  );
}
