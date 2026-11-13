import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { QuickScanShell } from "../components/QuickScanShell";
import { SeverityBadge } from "../components/SeverityBadge";
import { getTestCases, generateTestCases } from "../api/scans";
import type { TestCase, TestCaseType } from "../types";
import { ArrowLeft, TestTubeDiagonal, Wand2, Download, ChevronDown, ChevronUp, Loader2 } from "lucide-react";

const typeColours: Record<TestCaseType, string> = {
  manual: "bg-blue-100 text-blue-700",
  unit: "bg-purple-100 text-purple-700",
  smoke: "bg-gray-100 text-ink",
  regression: "bg-brand-50 text-brand-700",
  integration: "bg-teal-100 text-teal-700",
  performance: "bg-orange-100 text-orange-700",
  accessibility: "bg-emerald-100 text-emerald-700",
  security: "bg-red-100 text-red-700",
};

const allTypes: TestCaseType[] = ["manual", "unit", "smoke", "regression", "integration", "performance", "accessibility", "security"];

export function TestCasesPage() {
  const { id } = useParams<{ id: string }>();
  const [cases, setCases] = useState<TestCase[]>([]);
  const [typeFilter, setTypeFilter] = useState<TestCaseType | "all">("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [genMsg, setGenMsg] = useState("");

  useEffect(() => {
    if (id) getTestCases(id).then((r) => setCases(r.data));
  }, [id]);

  const handleGenerate = async () => {
    if (!id) return;
    setGenerating(true);
    setGenMsg("");
    try {
      const { data } = await generateTestCases(id);
      setGenMsg(data.message || "Test cases are being generated");
      setTimeout(() => {
        getTestCases(id).then((r) => setCases(r.data));
      }, 3000);
    } catch {
      setGenMsg("Generation failed. Please try again.");
    } finally {
      setGenerating(false);
    }
  };

  const filtered = typeFilter === "all" ? cases : cases.filter((c) => c.test_type === typeFilter);

  return (
    <QuickScanShell id={id} tab="tests">

      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <p className="text-body">{cases.length === 1 ? "1 test case" : `${cases.length} test cases`}</p>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="flex h-11 items-center gap-2 rounded-[10px] bg-brand-600 px-4 text-sm font-bold text-white hover:bg-brand-700 disabled:opacity-60"
        >
          {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wand2 className="w-4 h-4" />}
          Generate test cases
        </button>
      </div>

      {genMsg && (
        <div className="bg-brand-50 border border-brand-600 text-brand-700 text-sm rounded-lg px-4 py-3 mb-4">
          {genMsg}
        </div>
      )}

      {/* Type Filter */}
      <div className="flex flex-wrap gap-2 mb-6">
        <button
          onClick={() => setTypeFilter("all")}
          className={`min-h-[40px] px-4 rounded-full text-sm font-semibold ${
            typeFilter === "all" ? "bg-ink text-white" : "border border-gray-300 bg-white text-ink"
          }`}
        >
          All ({cases.length})
        </button>
        {allTypes.map((t) => {
          const count = cases.filter((c) => c.test_type === t).length;
          if (count === 0) return null;
          return (
            <button
              key={t}
              onClick={() => setTypeFilter(t)}
              className={`min-h-[40px] px-4 rounded-full text-sm font-semibold capitalize ${
                typeFilter === t ? "bg-ink text-white" : "border border-gray-300 bg-white text-ink"
              }`}
            >
              {t.replace(/_/g, " ")} ({count})
            </button>
          );
        })}
      </div>

      {/* Test Case Cards */}
      {filtered.length === 0 ? (
        <div className="text-center py-16 text-body bg-white border border-gray-300 rounded-2xl">
          <TestTubeDiagonal className="w-10 h-10 mx-auto mb-3 opacity-40" />
          <p className="font-medium">No test cases yet</p>
          <p className="text-sm mt-1">Choose Generate test cases to have them written for the pages this scan found.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((tc) => (
            <div key={tc.id} className="bg-white border border-gray-300 rounded-2xl overflow-hidden">
              <button
                onClick={() => setExpandedId(expandedId === tc.id ? null : tc.id)}
                className="w-full flex items-center gap-4 px-5 py-4 text-left hover:bg-soft transition"
              >
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold capitalize ${typeColours[tc.test_type]}`}>
                  {tc.test_type.replace(/_/g, " ")}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-ink text-sm">{tc.title}</p>
                </div>
                <span className="text-xs text-body font-mono">{tc.language}</span>
                <SeverityBadge severity={tc.priority} />
                <Download className="w-4 h-4 text-body hover:text-brand-600 shrink-0" />
                {expandedId === tc.id ? <ChevronUp className="w-4 h-4 text-body" /> : <ChevronDown className="w-4 h-4 text-body" />}
              </button>
              {expandedId === tc.id && (
                <div className="px-5 pb-5 bg-soft border-t border-gray-300 space-y-3">
                  {tc.preconditions && (
                    <div>
                      <h4 className="text-xs font-semibold text-body uppercase mb-1">Preconditions</h4>
                      <p className="text-sm text-ink">{tc.preconditions}</p>
                    </div>
                  )}
                  {tc.steps && (
                    <div>
                      <h4 className="text-xs font-semibold text-body uppercase mb-1">Test Steps</h4>
                      <pre className="bg-white border border-gray-300 text-sm p-3 rounded-lg overflow-x-auto whitespace-pre-wrap font-mono text-ink">{tc.steps}</pre>
                    </div>
                  )}
                  {tc.code && (
                    <div>
                      <h4 className="text-xs font-semibold text-body uppercase mb-1">Code</h4>
                      <pre className="bg-ink text-gray-100 text-xs p-4 rounded-lg overflow-x-auto font-mono">{tc.code}</pre>
                    </div>
                  )}
                  {tc.expected_result && (
                    <div>
                      <h4 className="text-xs font-semibold text-body uppercase mb-1">Expected Result</h4>
                      <p className="text-sm text-ink">{tc.expected_result}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </QuickScanShell>
  );
}
