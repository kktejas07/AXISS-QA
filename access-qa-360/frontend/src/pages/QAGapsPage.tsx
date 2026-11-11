import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Layout } from "../components/Layout";
import { CoverageHeatmap } from "../components/CoverageHeatmap";
import { SeverityBadge } from "../components/SeverityBadge";
import { getQAGaps } from "../api/scans";
import type { QAGap } from "../types";
import { ArrowLeft, BarChart3 } from "lucide-react";

export function QAGapsPage() {
  const { id } = useParams<{ id: string }>();
  const [gaps, setGaps] = useState<QAGap[]>([]);

  useEffect(() => {
    if (id) getQAGaps(id).then((r) => setGaps(r.data));
  }, [id]);

  const totalRoutes = gaps.length;
  const covered = gaps.filter((g) => g.coverage_status === "covered").length;
  const partial = gaps.filter((g) => g.coverage_status === "partial").length;
  const uncovered = gaps.filter((g) => g.coverage_status === "uncovered").length;
  const coveragePercent = totalRoutes > 0 ? Math.round((covered / totalRoutes) * 100) : 0;

  const gapsByType = gaps.reduce<Record<string, number>>((acc, g) => {
    acc[g.gap_type] = (acc[g.gap_type] || 0) + 1;
    return acc;
  }, {});

  return (
    <Layout>
      <Link
        to={`/scans/${id}`}
        className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-accent transition-colors mb-5"
      >
        <ArrowLeft className="w-3.5 h-3.5" /> Back to Scan Results
      </Link>

      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-fg flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-accent" /> QA Gap Analysis
        </h1>
        <p className="text-muted text-sm mt-0.5">Coverage analysis across all discovered routes</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
        <div className="bg-surface-1 border border-surface-3 rounded-card p-4 text-center">
          <p className="text-2xl font-bold text-fg">{totalRoutes}</p>
          <p className="text-xs text-muted mt-0.5">Total Routes</p>
        </div>
        <div className="bg-surface-1 border border-surface-3 rounded-card p-4 text-center">
          <p className="text-2xl font-bold text-accent">{coveragePercent}%</p>
          <p className="text-xs text-muted mt-0.5">Covered</p>
        </div>
        <div className="bg-surface-1 border border-surface-3 rounded-card p-4 text-center">
          <p className="text-2xl font-bold text-yellow-400">{partial}</p>
          <p className="text-xs text-muted mt-0.5">Partially Covered</p>
        </div>
        <div className="bg-surface-1 border border-surface-3 rounded-card p-4 text-center">
          <p className="text-2xl font-bold text-red-400">{uncovered}</p>
          <p className="text-xs text-muted mt-0.5">Uncovered</p>
        </div>
      </div>

      {/* Coverage Heatmap */}
      <div className="bg-surface-1 border border-surface-3 rounded-card p-5 mb-5">
        <h3 className="font-semibold text-fg mb-4 text-sm">Route Coverage Map</h3>
        <CoverageHeatmap gaps={gaps} />
      </div>

      {/* Gap Types Summary */}
      {Object.keys(gapsByType).length > 0 && (
        <div className="bg-surface-1 border border-surface-3 rounded-card p-5 mb-5">
          <h3 className="font-semibold text-fg mb-3 text-sm">Gaps by Category</h3>
          <div className="flex flex-wrap gap-2">
            {Object.entries(gapsByType).map(([type, count]) => (
              <span
                key={type}
                className="inline-flex items-center gap-2 px-3 py-1.5 bg-surface-2 border border-surface-3 rounded-badge text-sm text-fg-soft"
              >
                {type}
                <span className="bg-accent/15 text-accent text-xs font-bold px-1.5 py-0.5 rounded-badge border border-accent/30">
                  {count}
                </span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Gap List */}
      <div className="bg-surface-1 border border-surface-3 rounded-card overflow-hidden">
        <div className="px-5 py-3 border-b border-surface-3">
          <h3 className="font-semibold text-fg text-sm">All Gaps</h3>
        </div>
        {gaps.filter((g) => g.coverage_status !== "covered").length === 0 ? (
          <div className="text-center py-14 text-muted">
            <p className="font-medium text-fg-soft">Full coverage — no gaps detected</p>
          </div>
        ) : (
          <div className="divide-y divide-surface-3">
            {gaps
              .filter((g) => g.coverage_status !== "covered")
              .map((g) => (
                <div key={g.id} className="px-5 py-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-mono text-sm text-fg">{g.route}</span>
                        <SeverityBadge severity={g.risk_level} />
                      </div>
                      <p className="text-sm text-fg-soft">{g.description}</p>
                      {g.recommendation && (
                        <p className="text-xs text-accent mt-1">{g.recommendation}</p>
                      )}
                    </div>
                    <span className="text-xs bg-surface-2 border border-surface-3 text-muted px-2 py-0.5 rounded-badge shrink-0">
                      {g.gap_type}
                    </span>
                  </div>
                </div>
              ))}
          </div>
        )}
      </div>
    </Layout>
  );
}
