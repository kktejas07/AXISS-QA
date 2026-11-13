import type { Severity } from "../types";

const colours: Record<Severity, string> = {
  critical: "bg-red-700 text-white",
  high: "bg-orange-100 text-orange-900",
  medium: "bg-yellow-100 text-yellow-900",
  low: "bg-gray-100 text-gray-800",
  informational: "bg-gray-100 text-body",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className={`inline-flex items-center whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-bold capitalize ${colours[severity]}`}>
      {severity}
    </span>
  );
}
