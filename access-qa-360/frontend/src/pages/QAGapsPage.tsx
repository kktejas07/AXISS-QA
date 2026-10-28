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
      <Link to={`/scans/${id}`} className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-indigo-600 mb-4">
        <ArrowLeft className="w-4 h-4" /> Back to Scan Results
      </Link>

      <div className="mb-6">
        <h1 className="text-2xl font-bold text-brand-900 flex items-center gap-2">
          <BarChart3 className="w-6 h-6 text-indigo-500" /> QA Gap Analysis
        </h1>
        <p className="text-gray-500 text-sm mt-1">Coverage analysis across all discovered routes</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white border border-gray-200 rounded-xl p-4 text-center">
          <p className="text-2xl font-bold text-brand-900">{totalRoutes}</p>
          <p className="text-xs text-gray-500">Total Routes</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl p-4 text-center">
          <p className="text-2xl font-bold text-emerald-600">{coveragePercent}%</p>
          <p className="text-xs text-gray-500">Covered</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl p-4 text-center">
          <p className="text-2xl font-bold text-yellow-600">{partial}</p>
          <p className="text-xs text-gray-500">Partially Covered</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl p-4 text-center">
          <p className="text-2xl font-bold text-red-600">{uncovered}</p>
          <p className="text-xs text-gray-500">Uncovered</p>
        </div>
      </div>

      {/* Coverage Heatmap */}
      <div className="bg-white border border-gray-200 rounded-xl p-5 mb-6">
        <h3 className="font-semibold text-brand-900 mb-4">Route Coverage Map</h3>
        <CoverageHeatmap gaps={gaps} />
      </div>

      {/* Gap Types Summary */}
      {Object.keys(gapsByType).length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 mb-6">
          <h3 className="font-semibold text-brand-900 mb-3">Gaps by Category</h3>
          <div className="flex flex-wrap gap-2">
            {Object.entries(gapsByType).map(([type, count]) => (
              <span key={type} className="inline-flex items-center gap-1.5 px-3 py-1 bg-gray-100 rounded-full text-sm text-gray-700">
                {type} <span className="bg-indigo-100 text-indigo-700 text-xs font-bold px-1.5 py-0.5 rounded-full">{count}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Gap List */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-100">
          <h3 className="font-semibold text-brand-900">All Gaps</h3>
        </div>
        {gaps.filter(g => g.coverage_status !== "covered").length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <p className="font-medium">Full coverage — no gaps detected</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {gaps.filter(g => g.coverage_status !== "covered").map((g) => (
              <div key={g.id} className="px-5 py-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-mono text-sm text-brand-900">{g.route}</span>
                      <SeverityBadge severity={g.risk_level} />
                    </div>
                    <p className="text-sm text-gray-600">{g.description}</p>
                    {g.recommendation && (
                      <p className="text-xs text-indigo-600 mt-1">{g.recommendation}</p>
                    )}
                  </div>
                  <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded shrink-0">{g.gap_type}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Layout>
  );
}
