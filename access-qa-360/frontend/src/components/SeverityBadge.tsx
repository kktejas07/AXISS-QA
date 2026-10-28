import type { Severity } from "../types";

const colours: Record<Severity, string> = {
  critical: "bg-red-100 text-red-700",
  high: "bg-orange-100 text-orange-700",
  medium: "bg-yellow-100 text-yellow-800",
  low: "bg-blue-100 text-blue-700",
  informational: "bg-gray-100 text-gray-600",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${colours[severity]}`}>
      {severity.toUpperCase()}
    </span>
  );
}
