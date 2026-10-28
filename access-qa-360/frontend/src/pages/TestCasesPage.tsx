import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Layout } from "../components/Layout";
import { SeverityBadge } from "../components/SeverityBadge";
import { getTestCases, generateTestCases } from "../api/scans";
import type { TestCase, TestCaseType } from "../types";
import { ArrowLeft, TestTubeDiagonal, Wand2, Download, ChevronDown, ChevronUp, Loader2 } from "lucide-react";

const typeColours: Record<TestCaseType, string> = {
  manual: "bg-blue-100 text-blue-700",
  unit: "bg-purple-100 text-purple-700",
  smoke: "bg-gray-100 text-gray-700",
  regression: "bg-indigo-100 text-indigo-700",
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
      setGenMsg(data.message || "Test cases are being generated...");
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
      <Link to={`/scans/${id}`} className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-indigo-600 mb-4">
        <ArrowLeft className="w-4 h-4" /> Back to Scan Results
      </Link>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-brand-900 flex items-center gap-2">
            <TestTubeDiagonal className="w-6 h-6 text-indigo-500" /> Test Cases
          </h1>
          <p className="text-gray-500 text-sm mt-1">{cases.length} test cases generated</p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300 text-white text-sm font-semibold px-4 py-2 rounded-lg transition"
        >
          {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wand2 className="w-4 h-4" />}
          Generate Tests
        </button>
      </div>

      {genMsg && (
        <div className="bg-indigo-50 border border-indigo-200 text-indigo-700 text-sm rounded-lg px-4 py-3 mb-4">
          {genMsg}
        </div>
      )}

      {/* Type Filter */}
      <div className="flex flex-wrap gap-2 mb-6">
        <button
          onClick={() => setTypeFilter("all")}
          className={`px-3 py-1.5 rounded-full text-xs font-medium transition ${
            typeFilter === "all" ? "bg-indigo-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
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
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition capitalize ${
                typeFilter === t ? "bg-indigo-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {t} ({count})
            </button>
          );
        })}
      </div>

      {/* Test Case Cards */}
      {filtered.length === 0 ? (
        <div className="text-center py-16 text-gray-400 bg-white border border-gray-200 rounded-xl">
          <TestTubeDiagonal className="w-10 h-10 mx-auto mb-3 opacity-40" />
          <p className="font-medium">No test cases yet</p>
          <p className="text-sm mt-1">Click "Generate Tests" to create AI-powered test cases</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((tc) => (
            <div key={tc.id} className="bg-white border border-gray-200 rounded-xl overflow-hidden">
              <button
                onClick={() => setExpandedId(expandedId === tc.id ? null : tc.id)}
                className="w-full flex items-center gap-4 px-5 py-4 text-left hover:bg-gray-50 transition"
              >
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold capitalize ${typeColours[tc.test_type]}`}>
                  {tc.test_type}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-brand-900 text-sm">{tc.title}</p>
                </div>
                <span className="text-xs text-gray-400 font-mono">{tc.language}</span>
                <SeverityBadge severity={tc.priority} />
                <Download className="w-4 h-4 text-gray-400 hover:text-indigo-600 shrink-0" />
                {expandedId === tc.id ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
              </button>
              {expandedId === tc.id && (
                <div className="px-5 pb-5 bg-gray-50 border-t border-gray-100 space-y-3">
                  {tc.preconditions && (
                    <div>
                      <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">Preconditions</h4>
                      <p className="text-sm text-gray-700">{tc.preconditions}</p>
                    </div>
                  )}
                  {tc.steps && (
                    <div>
                      <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">Test Steps</h4>
                      <pre className="bg-white border border-gray-200 text-sm p-3 rounded-lg overflow-x-auto whitespace-pre-wrap font-mono text-gray-700">{tc.steps}</pre>
                    </div>
                  )}
                  {tc.code && (
                    <div>
                      <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">Code</h4>
                      <pre className="bg-brand-900 text-green-400 text-xs p-4 rounded-lg overflow-x-auto font-mono">{tc.code}</pre>
                    </div>
                  )}
                  {tc.expected_result && (
                    <div>
                      <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">Expected Result</h4>
                      <p className="text-sm text-gray-700">{tc.expected_result}</p>
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
