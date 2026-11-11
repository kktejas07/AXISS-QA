import type { Severity } from "../types";

const colours: Record<Severity, string> = {
  critical: "bg-red-900/40 text-red-400 border border-red-800/60",
  high: "bg-orange-900/40 text-orange-400 border border-orange-800/60",
  medium: "bg-yellow-900/40 text-yellow-400 border border-yellow-800/60",
  low: "bg-blue-900/40 text-blue-400 border border-blue-800/60",
  informational: "bg-surface-2 text-muted border border-surface-3",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-badge text-xs font-semibold tracking-wide ${colours[severity]}`}
    >
      {severity.toUpperCase()}
    </span>
  );
}
