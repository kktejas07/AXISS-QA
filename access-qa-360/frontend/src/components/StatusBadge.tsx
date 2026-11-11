import type { RunStatus } from "../types";

const colours: Record<RunStatus, string> = {
  passed: "bg-emerald-900/40 text-emerald-400 border border-emerald-800/60",
  failed: "bg-red-900/40 text-red-400 border border-red-800/60",
  running: "bg-accent/20 text-accent border border-accent/40 animate-pulse",
  queued: "bg-surface-2 text-muted border border-surface-3",
  error: "bg-orange-900/40 text-orange-400 border border-orange-800/60",
};

export function StatusBadge({ status }: { status: RunStatus }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-badge text-xs font-semibold tracking-wide ${colours[status]}`}
    >
      {status.toUpperCase()}
    </span>
  );
}
