import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Layout } from "../components/Layout";
import { SeverityBadge } from "../components/SeverityBadge";
import { getTestCases, generateTestCases } from "../api/scans";
import type { TestCase, TestCaseType } from "../types";
import { ArrowLeft, TestTubeDiagonal, Wand2, Download, ChevronDown, ChevronUp, Loader2 } from "lucide-react";

const typeColours: Record<TestCaseType, string> = {
  manual: "bg-blue-900/30 text-blue-400 border border-blue-800/40",
  unit: "bg-purple-900/30 text-purple-400 border border-purple-800/40",
  smoke: "bg-surface-2 text-muted border border-surface-3",
  regression: "bg-indigo-900/30 text-indigo-400 border border-indigo-800/40",
  integration: "bg-teal-900/30 text-teal-400 border border-teal-800/40",
  performance: "bg-orange-900/30 text-orange-400 border border-orange-800/40",
  accessibility: "bg-emerald-900/30 text-emerald-400 border border-emerald-800/40",
  security: "bg-red-900/30 text-red-400 border border-red-800/40",
};

const allTypes: TestCaseType[] = [
  "manual", "unit", "smoke", "regression", "integration",
  "performance", "accessibility", "security",
];

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
      setGenMsg(data.message || "Test cases are being generated…");
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
    <Layout>
      <Link
        to={`/scans/${id}`}
        className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-accent transition-colors mb-5"
      >
        <ArrowLeft className="w-3.5 h-3.5" /> Back to Scan Results
      </Link>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-fg flex items-center gap-2">
            <TestTubeDiagonal className="w-5 h-5 text-accent" /> Test Cases
          </h1>
          <p className="text-muted text-sm mt-0.5">{cases.length} test cases generated</p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="refero-btn-primary flex items-center gap-2 px-4 py-2 text-sm"
        >
          {generating ? (
            <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Generating…</>
          ) : (
            <><Wand2 className="w-3.5 h-3.5" /> Generate Tests</>
          )}
        </button>
      </div>

      {genMsg && (
        <div className="bg-accent/10 border border-accent/30 text-accent text-sm rounded-card px-4 py-3 mb-5">
          {genMsg}
        </div>
      )}

      {/* Type Filter */}
      <div className="flex flex-wrap gap-2 mb-6">
        <button
          onClick={() => setTypeFilter("all")}
          className={`px-3 py-1.5 rounded-badge text-xs font-medium border transition-colors ${
            typeFilter === "all"
              ? "bg-accent text-app border-accent"
              : "bg-surface-1 border-surface-3 text-muted hover:border-accent/50 hover:text-fg"
          }`}
        >
          All ({cases.length})
        </button>
        {allTypes.map((t) => {
          const count = cases.filter((c) => c.test_type === t).length;
          return (
            <button
              key={t}
              onClick={() => setTypeFilter(t)}
              className={`px-3 py-1.5 rounded-badge text-xs font-medium border transition-colors capitalize ${
                typeFilter === t
                  ? "bg-accent text-app border-accent"
                  : "bg-surface-1 border-surface-3 text-muted hover:border-accent/50 hover:text-fg"
              }`}
            >
              {t} ({count})
            </button>
          );
        })}
      </div>

      {/* Test Case Cards */}
      {filtered.length === 0 ? (
        <div className="text-center py-16 text-muted bg-surface-1 border border-surface-3 rounded-card">
          <TestTubeDiagonal className="w-8 h-8 mx-auto mb-3 opacity-30" />
          <p className="font-medium text-fg-soft">No test cases yet</p>
          <p className="text-sm mt-1">Click "Generate Tests" to create AI-powered test cases</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((tc) => (
            <div key={tc.id} className="bg-surface-1 border border-surface-3 rounded-card overflow-hidden">
              <button
                onClick={() => setExpandedId(expandedId === tc.id ? null : tc.id)}
                className="w-full flex items-center gap-4 px-5 py-4 text-left hover:bg-surface-2 transition-colors"
              >
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-badge text-xs font-semibold capitalize ${typeColours[tc.test_type]}`}>
                  {tc.test_type}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-fg text-sm">{tc.title}</p>
                </div>
                <span className="text-xs text-muted font-mono">{tc.language}</span>
                <SeverityBadge severity={tc.priority} />
                <Download className="w-4 h-4 text-muted hover:text-accent shrink-0 transition-colors" />
                {expandedId === tc.id ? (
                  <ChevronUp className="w-4 h-4 text-muted-dim shrink-0" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-muted-dim shrink-0" />
                )}
              </button>
              {expandedId === tc.id && (
                <div className="px-5 pb-5 bg-surface-2 border-t border-surface-3 space-y-4 pt-4">
                  {tc.preconditions && (
                    <div>
                      <h4 className="text-xs font-semibold text-muted uppercase tracking-wider mb-1.5">
                        Preconditions
                      </h4>
                      <p className="text-sm text-fg-soft">{tc.preconditions}</p>
                    </div>
                  )}
                  {tc.steps && (
                    <div>
                      <h4 className="text-xs font-semibold text-muted uppercase tracking-wider mb-1.5">
                        Test Steps
                      </h4>
                      <pre className="bg-app border border-surface-3 text-fg-soft text-xs p-3 rounded-card overflow-x-auto whitespace-pre-wrap font-mono">
                        {tc.steps}
                      </pre>
                    </div>
                  )}
                  {tc.code && (
                    <div>
                      <h4 className="text-xs font-semibold text-muted uppercase tracking-wider mb-1.5">
                        Code
                      </h4>
                      <pre className="bg-app border border-surface-3 text-emerald-400 text-xs p-4 rounded-card overflow-x-auto font-mono">
                        {tc.code}
                      </pre>
                    </div>
                  )}
                  {tc.expected_result && (
                    <div>
                      <h4 className="text-xs font-semibold text-muted uppercase tracking-wider mb-1.5">
                        Expected Result
                      </h4>
                      <p className="text-sm text-fg-soft">{tc.expected_result}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </Layout>
  );
}
