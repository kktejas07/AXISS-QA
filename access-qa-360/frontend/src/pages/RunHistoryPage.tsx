import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Layout } from "../components/Layout";
import { getRuns, triggerRun } from "../api/runs";
import { StatusBadge } from "../components/StatusBadge";
import type { Run } from "../types";
import { Play, GitBranch, Clock } from "lucide-react";

export function RunHistoryPage() {
  const { projectId, suiteId } = useParams<{ projectId: string; suiteId: string }>();
  const [runs, setRuns] = useState<Run[]>([]);
  const [triggering, setTriggering] = useState(false);

  const loadRuns = () => {
    if (projectId && suiteId) getRuns(projectId, suiteId).then((r) => setRuns(r.data));
  };

  useEffect(() => {
    loadRuns();
  }, [projectId, suiteId]);

  const handleTrigger = async () => {
    if (!projectId || !suiteId) return;
    setTriggering(true);
    try {
      await triggerRun(projectId, suiteId);
      setTimeout(loadRuns, 1000);
    } finally {
      setTriggering(false);
    }
  };

  return (
    <Layout>
      <div className="flex items-center justify-between mb-6">
        <div>
          <Link to={`/projects/${projectId}/suites`} className="text-sm text-indigo-600 hover:underline">
            &larr; Suites
          </Link>
          <h1 className="text-2xl font-bold text-brand-900 mt-1">Run History</h1>
        </div>
        <button
          onClick={handleTrigger}
          disabled={triggering}
          className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 disabled:opacity-60 text-white text-sm font-semibold px-4 py-2 rounded-lg transition"
        >
          <Play className="w-4 h-4" /> {triggering ? "Queuing…" : "Run Now"}
        </button>
      </div>
      <div className="space-y-3">
        {runs.map((run) => (
          <div key={run.id} className="bg-white border border-gray-200 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <StatusBadge status={run.status} />
              <span className="text-xs font-mono text-gray-400">
                {new Date(run.created_at).toLocaleString()}
              </span>
            </div>
            <div className="flex flex-wrap gap-4 text-sm text-gray-600 mt-2">
              {run.branch && (
                <span className="flex items-center gap-1">
                  <GitBranch className="w-3.5 h-3.5" />
                  {run.branch}
                </span>
              )}
              {run.duration_ms != null && (
                <span className="flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5" />
                  {(run.duration_ms / 1000).toFixed(1)}s
                </span>
              )}
              {run.tests_total != null && (
                <span>
                  {run.tests_passed}/{run.tests_total} passed
                </span>
              )}
            </div>
            {run.triage_summary && (
              <div className="mt-3 bg-red-50 border border-red-100 rounded-lg p-3 text-xs text-red-700 whitespace-pre-line">
                {run.triage_summary}
              </div>
            )}
          </div>
        ))}
        {runs.length === 0 && (
          <p className="text-center text-gray-400 py-12">
            No runs yet. Click "Run Now" to start your first test run.
          </p>
        )}
      </div>
    </Layout>
  );
}
