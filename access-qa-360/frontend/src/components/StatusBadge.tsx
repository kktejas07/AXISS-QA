import type { RunStatus } from "../types";

const colours: Record<RunStatus, string> = {
  passed: "bg-emerald-100 text-emerald-800",
  failed: "bg-red-100 text-red-800",
  running: "bg-brand-50 text-brand-700 ",
  queued: "bg-gray-100 text-body",
  error: "bg-orange-100 text-orange-900",
};

export function StatusBadge({ status }: { status: RunStatus }) {
  return (
    <span className={`inline-flex items-center whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-bold capitalize ${colours[status]}`}>
      {status}
    </span>
  );
}
