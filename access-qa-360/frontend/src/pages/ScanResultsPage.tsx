import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Layout } from "../components/Layout";
import { getScan } from "../api/scans";
import type { Scan } from "../types";
import { Shield, Bug, TestTubeDiagonal, FileText, ArrowLeft, Loader2 } from "lucide-react";

const gradeColour: Record<string, string> = {
  A: "text-emerald-400 bg-emerald-900/30 border-emerald-700/50",
  B: "text-accent bg-accent/15 border-accent/40",
  C: "text-yellow-400 bg-yellow-900/30 border-yellow-700/50",
  D: "text-orange-400 bg-orange-900/30 border-orange-700/50",
  F: "text-red-400 bg-red-900/30 border-red-700/50",
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
          <div className="w-6 h-6 border-2 border-surface-3 border-t-accent rounded-full animate-spin" />
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
      <Link
        to="/"
        className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-accent transition-colors mb-5"
      >
        <ArrowLeft className="w-3.5 h-3.5" /> Back to Dashboard
      </Link>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-fg">Scan Results</h1>
          <p className="text-muted text-sm mt-0.5 font-mono">{scan.url}</p>
        </div>
        <span
          className={`px-2.5 py-1 rounded-badge text-xs font-semibold border ${
            scan.status === "completed"
              ? "bg-emerald-900/20 text-emerald-400 border-emerald-800/40"
              : scan.status === "failed"
              ? "bg-red-900/20 text-red-400 border-red-800/40"
              : "bg-accent/15 text-accent border-accent/30 animate-pulse"
          }`}
        >
          {scan.status.toUpperCase()}
        </span>
      </div>

      {/* Tabs */}
      <div className="border-b border-surface-3 mb-6">
        <nav className="flex gap-1">
          {tabs.map((t) =>
            t.key === "overview" ? (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`pb-3 px-3 text-sm font-medium border-b-2 transition-colors ${
                  tab === t.key
                    ? "border-accent text-accent"
                    : "border-transparent text-muted hover:text-fg"
                }`}
              >
                {t.label}
              </button>
            ) : (
              <Link
                key={t.key}
                to={tabRoutes[t.key]}
                className="pb-3 px-3 text-sm font-medium border-b-2 border-transparent text-muted hover:text-fg transition-colors"
              >
                {t.label}
              </Link>
            )
          )}
        </nav>
      </div>

      {/* Overview Tab */}
      {tab === "overview" && (
        <div className="space-y-5">
          {/* Risk Scorecard */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div
              className={`border rounded-card p-5 text-center ${
                gradeColour[scan.risk_grade] || gradeColour.C
              }`}
            >
              <p className="text-5xl font-bold font-display">{scan.risk_grade}</p>
              <p className="text-xs mt-1 opacity-70 uppercase tracking-wider">Risk Grade</p>
            </div>
            <div className="bg-surface-1 border border-surface-3 rounded-card p-5 text-center">
              <p className="text-3xl font-bold text-fg">{scan.coverage_percent}%</p>
              <p className="text-xs text-muted mt-1">QA Coverage</p>
            </div>
            <div className="bg-surface-1 border border-surface-3 rounded-card p-5 text-center">
              <p className="text-3xl font-bold text-fg">{totalVulns}</p>
              <p className="text-xs text-muted mt-1">Vulnerabilities</p>
            </div>
            <div className="bg-surface-1 border border-surface-3 rounded-card p-5 text-center">
              <p className="text-3xl font-bold text-fg">{scan.test_cases_generated}</p>
              <p className="text-xs text-muted mt-1">Test Cases</p>
            </div>
          </div>

          {/* Vulnerability Breakdown */}
          <div className="bg-surface-1 border border-surface-3 rounded-card p-5">
            <h3 className="font-semibold text-fg mb-4 flex items-center gap-2 text-sm">
              <Shield className="w-4 h-4 text-accent" /> Vulnerability Breakdown
            </h3>
            <div className="grid grid-cols-5 gap-3">
              {[
                { label: "Critical", count: vc.critical, bg: "bg-red-900/40 text-red-400 border border-red-800/50" },
                { label: "High", count: vc.high, bg: "bg-orange-900/40 text-orange-400 border border-orange-800/50" },
                { label: "Medium", count: vc.medium, bg: "bg-yellow-900/40 text-yellow-400 border border-yellow-800/50" },
                { label: "Low", count: vc.low, bg: "bg-blue-900/40 text-blue-400 border border-blue-800/50" },
                { label: "Info", count: vc.informational, bg: "bg-surface-2 text-muted border border-surface-3" },
              ].map((v) => (
                <div key={v.label} className="text-center">
                  <div className={`${v.bg} text-xl font-bold rounded-card py-3`}>{v.count}</div>
                  <p className="text-xs text-muted mt-1.5">{v.label}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Quick Links */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {[
              {
                to: `/scans/${id}/vulnerabilities`,
                icon: Bug,
                iconColor: "text-red-400",
                iconBg: "bg-red-900/20",
                title: "Vulnerabilities",
                desc: "View all findings with evidence",
              },
              {
                to: `/scans/${id}/test-cases`,
                icon: TestTubeDiagonal,
                iconColor: "text-accent",
                iconBg: "bg-accent/10",
                title: "Test Cases",
                desc: "AI-generated test suites",
              },
              {
                to: `/scans/${id}/reports`,
                icon: FileText,
                iconColor: "text-emerald-400",
                iconBg: "bg-emerald-900/20",
                title: "Reports",
                desc: "Export PDF, Word, JSON",
              },
            ].map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className="flex items-center gap-3 bg-surface-1 border border-surface-3 rounded-card p-4 hover:bg-surface-2 hover:border-accent/40 transition-colors group"
              >
                <div className={`w-10 h-10 rounded-badge ${item.iconBg} flex items-center justify-center shrink-0`}>
                  <item.icon className={`w-5 h-5 ${item.iconColor}`} />
                </div>
                <div>
                  <p className="font-semibold text-fg text-sm group-hover:text-accent transition-colors">
                    {item.title}
                  </p>
                  <p className="text-xs text-muted">{item.desc}</p>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </Layout>
  );
}
