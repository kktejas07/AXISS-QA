import type { RunStatus } from "../types";

const colours: Record<RunStatus, string> = {
  passed: "bg-emerald-100 text-emerald-700",
  failed: "bg-red-100 text-red-700",
  running: "bg-indigo-100 text-indigo-700 animate-pulse",
  queued: "bg-gray-100 text-gray-600",
  error: "bg-orange-100 text-orange-700",
};

export function StatusBadge({ status }: { status: RunStatus }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${colours[status]}`}>
      {status.toUpperCase()}
    </span>
  );
}
