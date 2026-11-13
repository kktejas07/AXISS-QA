import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Clock, GitBranch, Play } from "lucide-react";
import { Layout } from "../components/Layout";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { StatusBadge } from "../components/StatusBadge";
import { getRuns, triggerRun } from "../api/runs";
import type { Run } from "../types";
import { apiError } from "../utils/errors";
import { backLink, card, emptyState, errorBox, pageTitle, primaryButton } from "../components/ui";

export function RunHistoryPage() {
  const { projectId, suiteId } = useParams<{ projectId: string; suiteId: string }>();
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState("");

  const active = runs?.some((r) => r.status === "queued" || r.status === "running") ?? false;

  useEffect(() => {
    if (!projectId || !suiteId) return;
    let alive = true;
    const load = () =>
      getRuns(projectId, suiteId)
        .then((r) => alive && setRuns(r.data))
        .catch(() => alive && setError("The runs could not be loaded. Reload the page."));
    load();
    // Keep asking only while a run is still going.
    const timer = active ? setInterval(load, 3000) : undefined;
    return () => {
      alive = false;
      if (timer) clearInterval(timer);
    };
  }, [projectId, suiteId, active]);

  const handleTrigger = async () => {
    if (!projectId || !suiteId) return;
    setError("");
    setTriggering(true);
    try {
      const { data } = await triggerRun(projectId, suiteId);
      setRuns((list) => [data, ...(list ?? [])]);
    } catch (err) {
      setError(apiError(err, "The run could not be started. Try again."));
    } finally {
      setTriggering(false);
    }
  };

  return (
    <Layout>
      <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link to={`/projects/${projectId}/suites`} className={backLink}>Test suites</Link>
          <h1 className={`${pageTitle} mt-1`}>Runs</h1>
        </div>
        <button type="button" onClick={handleTrigger} disabled={triggering} className={primaryButton}>
          <Play className="h-[18px] w-[18px]" aria-hidden="true" />
          {triggering ? "Starting" : "Run now"}
        </button>
      </div>
      {error && <p role="alert" className={`${errorBox} mb-5`}>{error}</p>}
      {!runs ? (
        !error && <LoadingSpinner />
      ) : runs.length === 0 ? (
        <p className={emptyState}>This suite has not been run yet. Choose Run now to try it against your app.</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {runs.map((run) => (
            <li key={run.id} className={`${card} p-5`}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <StatusBadge status={run.status} />
                <span className="text-[13.5px] text-body">{new Date(run.created_at).toLocaleString()}</span>
              </div>
              <div className="mt-2.5 flex flex-wrap gap-x-5 gap-y-1 text-[14.5px] text-body">
                {run.tests_total != null && (
                  <span className="font-semibold text-ink">{run.tests_passed} of {run.tests_total} tests passed</span>
                )}
                {run.duration_ms != null && (
                  <span className="flex items-center gap-1.5">
                    <Clock className="h-4 w-4" aria-hidden="true" />
                    {(run.duration_ms / 1000).toFixed(1)} seconds
                  </span>
                )}
                {run.branch && (
                  <span className="flex items-center gap-1.5 font-mono text-[13px]">
                    <GitBranch className="h-4 w-4" aria-hidden="true" />
                    {run.branch}
                  </span>
                )}
              </div>
              {run.triage_summary && (
                <div className="mt-3 whitespace-pre-line rounded-[10px] border border-red-200 bg-red-50 px-4 py-3 text-[14.5px] text-red-900">
                  <p className="mb-1 text-[13px] font-bold">Why it failed</p>
                  {run.triage_summary}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </Layout>
  );
}
