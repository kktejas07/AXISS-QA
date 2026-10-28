import { StatusBadge } from "./StatusBadge";
import type { Run } from "../types";
import { GitBranch, Clock } from "lucide-react";

export function RunCard({ run }: { run: Run }) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4">
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
  );
}
