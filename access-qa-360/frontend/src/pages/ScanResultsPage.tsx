import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Layout } from "../components/Layout";
import { getScan } from "../api/scans";
import type { Scan } from "../types";
import { Shield, Bug, TestTubeDiagonal, FileText, ArrowLeft, Loader2 } from "lucide-react";

const gradeColour: Record<string, string> = {
  A: "text-emerald-600 bg-emerald-50 border-emerald-200",
  B: "text-blue-600 bg-blue-50 border-blue-200",
  C: "text-yellow-600 bg-yellow-50 border-yellow-200",
  D: "text-orange-600 bg-orange-50 border-orange-200",
  F: "text-red-600 bg-red-50 border-red-200",
};

export function ScanResultsPage() {
  const { id } = useParams<{ id: string }>();
  const [scan, setScan] = useState<Scan | null>(null);
  const [tab, setTab] = useState<"overview" | "vulns" | "gaps" | "tests" | "reports">("overview");

  useEffect(() => {
    if (id) getScan(id).then((r) => setScan(r.data));
  }, [id]);

  if (!scan) {
    return (
      <Layout>
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
        </div>
      </Layout>
    );
  }

  const vc = scan.vulnerability_count;
  const totalVulns = vc.critical + vc.high + vc.medium + vc.low + vc.informational;
  const tabs = [
    { key: "overview" as const, label: "Overview" },
    { key: "vulns" as const, label: `Vulnerabilities (${totalVulns})` },
    { key: "gaps" as const, label: "QA Gaps" },
    { key: "tests" as const, label: `Test Cases (${scan.test_cases_generated})` },
    { key: "reports" as const, label: "Reports" },
  ];

  const tabRoutes: Record<string, string> = {
    vulns: `/scans/${id}/vulnerabilities`,
    gaps: `/scans/${id}/gaps`,
    tests: `/scans/${id}/test-cases`,
    reports: `/scans/${id}/reports`,
  };

  return (
    <Layout>
      <Link to="/" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-indigo-600 mb-4">
        <ArrowLeft className="w-4 h-4" /> Back to Dashboard
      </Link>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-brand-900">Scan Results</h1>
          <p className="text-gray-500 text-sm mt-1 font-mono">{scan.url}</p>
        </div>
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
            scan.status === "completed" ? "bg-emerald-100 text-emerald-700" :
            scan.status === "failed" ? "bg-red-100 text-red-700" :
            "bg-indigo-100 text-indigo-700 animate-pulse"
          }`}>
            {scan.status.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-6">
          {tabs.map((t) => (
            t.key === "overview" ? (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`pb-3 text-sm font-medium border-b-2 transition ${
                  tab === t.key
                    ? "border-indigo-500 text-indigo-600"
                    : "border-transparent text-gray-500 hover:text-gray-700"
                }`}
              >
                {t.label}
              </button>
            ) : (
              <Link
                key={t.key}
                to={tabRoutes[t.key]}
                className="pb-3 text-sm font-medium border-b-2 border-transparent text-gray-500 hover:text-indigo-600 transition"
              >
                {t.label}
              </Link>
            )
          ))}
        </nav>
      </div>

      {/* Overview Tab */}
      {tab === "overview" && (
        <div className="space-y-6">
          {/* Risk Scorecard */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className={`border rounded-xl p-5 text-center ${gradeColour[scan.risk_grade] || gradeColour.C}`}>
              <p className="text-5xl font-bold">{scan.risk_grade}</p>
              <p className="text-sm mt-1 opacity-70">Risk Grade</p>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-5 text-center">
              <p className="text-3xl font-bold text-brand-900">{scan.coverage_percent}%</p>
              <p className="text-sm text-gray-500 mt-1">QA Coverage</p>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-5 text-center">
              <p className="text-3xl font-bold text-brand-900">{totalVulns}</p>
              <p className="text-sm text-gray-500 mt-1">Vulnerabilities</p>
            </div>
            <div className="bg-white border border-gray-200 rounded-xl p-5 text-center">
              <p className="text-3xl font-bold text-brand-900">{scan.test_cases_generated}</p>
              <p className="text-sm text-gray-500 mt-1">Test Cases</p>
            </div>
          </div>

          {/* Vulnerability Breakdown */}
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <h3 className="font-semibold text-brand-900 mb-4 flex items-center gap-2">
              <Shield className="w-5 h-5 text-indigo-500" /> Vulnerability Breakdown
            </h3>
            <div className="grid grid-cols-5 gap-3">
              {[
                { label: "Critical", count: vc.critical, colour: "bg-red-500" },
                { label: "High", count: vc.high, colour: "bg-orange-500" },
                { label: "Medium", count: vc.medium, colour: "bg-yellow-500" },
                { label: "Low", count: vc.low, colour: "bg-blue-500" },
                { label: "Info", count: vc.informational, colour: "bg-gray-400" },
              ].map((v) => (
                <div key={v.label} className="text-center">
                  <div className={`${v.colour} text-white text-xl font-bold rounded-lg py-3`}>
                    {v.count}
                  </div>
                  <p className="text-xs text-gray-500 mt-1.5">{v.label}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Quick Links */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Link
              to={`/scans/${id}/vulnerabilities`}
              className="flex items-center gap-3 bg-white border border-gray-200 rounded-xl p-4 hover:border-indigo-300 transition group"
            >
              <Bug className="w-8 h-8 text-red-500" />
              <div>
                <p className="font-semibold text-brand-900 group-hover:text-indigo-600">Vulnerabilities</p>
                <p className="text-xs text-gray-500">View all findings with evidence</p>
              </div>
            </Link>
            <Link
              to={`/scans/${id}/test-cases`}
              className="flex items-center gap-3 bg-white border border-gray-200 rounded-xl p-4 hover:border-indigo-300 transition group"
            >
              <TestTubeDiagonal className="w-8 h-8 text-indigo-500" />
              <div>
                <p className="font-semibold text-brand-900 group-hover:text-indigo-600">Test Cases</p>
                <p className="text-xs text-gray-500">AI-generated test suites</p>
              </div>
            </Link>
            <Link
              to={`/scans/${id}/reports`}
              className="flex items-center gap-3 bg-white border border-gray-200 rounded-xl p-4 hover:border-indigo-300 transition group"
            >
              <FileText className="w-8 h-8 text-emerald-500" />
              <div>
                <p className="font-semibold text-brand-900 group-hover:text-indigo-600">Reports</p>
                <p className="text-xs text-gray-500">Export PDF, Word, JSON</p>
              </div>
            </Link>
          </div>
        </div>
      )}
    </Layout>
  );
}
