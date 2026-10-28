import type { QAGap, CoverageStatus } from "../types";

const statusColour: Record<CoverageStatus, string> = {
  covered: "bg-emerald-400",
  partial: "bg-yellow-400",
  uncovered: "bg-red-400",
};

const statusLabel: Record<CoverageStatus, string> = {
  covered: "Covered",
  partial: "Partial",
  uncovered: "Uncovered",
};

export function CoverageHeatmap({ gaps }: { gaps: QAGap[] }) {
  if (gaps.length === 0) {
    return <p className="text-gray-400 text-sm">No route data available.</p>;
  }

  return (
    <div>
      <div className="flex gap-4 mb-4 text-xs text-gray-500">
        {(Object.keys(statusColour) as CoverageStatus[]).map((s) => (
          <div key={s} className="flex items-center gap-1.5">
            <div className={`w-3 h-3 rounded ${statusColour[s]}`} />
            {statusLabel[s]}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2">
        {gaps.map((g) => (
          <div
            key={g.id}
            className={`${statusColour[g.coverage_status]} bg-opacity-20 border border-gray-200 rounded-lg p-3 text-xs`}
            title={`${g.route} — ${g.coverage_status}`}
          >
            <div className={`w-2 h-2 rounded-full ${statusColour[g.coverage_status]} mb-1.5`} />
            <p className="font-mono text-gray-700 truncate">{g.route}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
