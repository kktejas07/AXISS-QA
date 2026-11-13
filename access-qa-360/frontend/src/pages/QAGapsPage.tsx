import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { QuickScanShell } from "../components/QuickScanShell";
import { SeverityBadge } from "../components/SeverityBadge";
import { getQAGaps } from "../api/scans";
import type { QAGap } from "../types";
import { card, emptyState, errorBox } from "../components/ui";

const typeName: Record<string, string> = {
  uncovered: "No tests",
  partially_covered: "Partly tested",
  missing_edge_case: "Missing edge case",
  accessibility: "Accessibility",
  business_logic: "Business rule",
  orphaned_test: "Test with no route",
};
const riskOrder = ["critical", "high", "medium", "low", "informational"];

/** Routes and flows of a quick scan that do not have enough tests. */
export function QAGapsPage() {
  const { id } = useParams<{ id: string }>();
  const [gaps, setGaps] = useState<QAGap[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [type, setType] = useState("all");

  useEffect(() => {
    if (id) getQAGaps(id).then((r) => setGaps(r.data)).catch(() => setFailed(true));
  }, [id]);

  const byType = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const g of gaps ?? []) counts[g.gap_type] = (counts[g.gap_type] ?? 0) + 1;
    return Object.entries(counts).sort((a, b) => b[1] - a[1]);
  }, [gaps]);
  const shown = useMemo(
    () => (gaps ?? []).filter((g) => type === "all" || g.gap_type === type).sort((a, b) => riskOrder.indexOf(a.risk_level) - riskOrder.indexOf(b.risk_level)),
    [gaps, type]
  );
  const serious = (gaps ?? []).filter((g) => g.risk_level === "critical" || g.risk_level === "high").length;

  return (
    <QuickScanShell id={id} tab="gaps">
      {failed ? (
        <p role="alert" className={errorBox}>The QA gaps could not be loaded. Reload the page.</p>
      ) : !gaps ? (
        <LoadingSpinner />
      ) : gaps.length === 0 ? (
        <p className={emptyState}>No gaps were found: every route this scan mapped has tests.</p>
      ) : (
        <div className="flex flex-col gap-6">
          <dl className={`${card} grid overflow-hidden sm:grid-cols-3`}>
            {[
              ["Gaps found", gaps.length],
              ["High or critical risk", serious],
              ["Routes with no tests at all", gaps.filter((g) => g.gap_type === "uncovered").length],
            ].map(([label, value]) => (
              <div key={label} className="border-b border-line px-6 py-5 last:border-b-0 sm:border-b-0 sm:border-r sm:last:border-r-0">
                <dt className="text-sm font-semibold text-body">{label}</dt>
                <dd className="text-[28px] font-extrabold leading-tight">{value}</dd>
              </div>
            ))}
          </dl>

          <div role="group" aria-label="Kind of gap" className="flex flex-wrap gap-2">
            {[["all", "All", gaps.length] as const, ...byType.map(([t, n]) => [t, typeName[t] ?? t, n] as const)].map(([key, text, count]) => (
              <button
                key={key}
                type="button"
                aria-pressed={type === key}
                onClick={() => setType(key)}
                className={`flex min-h-[44px] items-center gap-2 rounded-full border px-4 text-sm font-semibold ${type === key ? "border-ink bg-ink text-white" : "border-gray-300 bg-white"}`}
              >
                {text}
                <span className={`rounded-full px-2 text-[13px] font-bold text-ink ${type === key ? "bg-white" : "bg-gray-100"}`}>{count}</span>
              </button>
            ))}
          </div>

          <ul className={`${card} overflow-hidden`}>
            {shown.map((g, i) => (
              <li key={g.id} className={`flex flex-col gap-1.5 px-5 py-4 ${i ? "border-t border-line" : ""}`}>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
                  <SeverityBadge severity={g.risk_level} />
                  <span className="break-all font-mono text-sm font-medium">{g.route_path}</span>
                  <span className="text-[13.5px] text-body">{typeName[g.gap_type] ?? g.gap_type}</span>
                </div>
                <p>{g.description}</p>
                {g.recommendation && (
                  <p className="text-[14.5px] text-body">
                    <span className="font-semibold text-ink">What to add: </span>
                    {g.recommendation}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </QuickScanShell>
  );
}
