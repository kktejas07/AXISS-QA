import type { QAGap, CoverageStatus } from "../types";

const statusConfig: Record<CoverageStatus, { dot: string; card: string; label: string }> = {
  covered:   { dot: "bg-emerald-400", card: "bg-emerald-900/20 border-emerald-800/40", label: "Covered" },
  partial:   { dot: "bg-yellow-400",  card: "bg-yellow-900/20 border-yellow-800/40",   label: "Partial" },
  uncovered: { dot: "bg-red-400",     card: "bg-red-900/20 border-red-800/40",          label: "Uncovered" },
};

export function CoverageHeatmap({ gaps }: { gaps: QAGap[] }) {
  if (gaps.length === 0) {
    return <p className="text-muted text-sm">No route data available.</p>;
  }

  return (
    <div>
      {/* Legend */}
      <div className="flex gap-4 mb-4 text-xs text-muted">
        {(Object.keys(statusConfig) as CoverageStatus[]).map((s) => (
          <div key={s} className="flex items-center gap-1.5">
            <div className={`w-2.5 h-2.5 rounded-full ${statusConfig[s].dot}`} />
            {statusConfig[s].label}
          </div>
        ))}
      </div>

      {/* Heatmap grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2">
        {gaps.map((g) => {
          const cfg = statusConfig[g.coverage_status];
          return (
            <div
              key={g.id}
              className={`${cfg.card} border rounded-badge p-3 text-xs`}
              title={`${g.route} — ${g.coverage_status}`}
            >
              <div className={`w-2 h-2 rounded-full ${cfg.dot} mb-1.5`} />
              <p className="font-mono text-fg-soft truncate">{g.route}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
