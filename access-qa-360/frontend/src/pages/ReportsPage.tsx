import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Layout } from "../components/Layout";
import { getReports, generateReport } from "../api/scans";
import type { Report, ReportType, ReportFormat } from "../types";
import { ArrowLeft, FileText, Download, Loader2, Plus } from "lucide-react";

const reportTypeLabels: Record<ReportType, string> = {
  executive: "Executive Summary",
  vulnerability: "Vulnerability Report",
  "qa-gap": "QA Gap Report",
  "test-bundle": "Test Case Bundle",
  compliance: "Compliance Report",
  diff: "Diff Report",
};

const formatLabels: Record<ReportFormat, string> = {
  pdf: "PDF",
  json: "JSON",
  docx: "Word (.docx)",
  csv: "CSV",
  feature: "Gherkin (.feature)",
  py: "Python (.py)",
  ts: "TypeScript (.ts)",
};

const reportFormatOptions: Record<ReportType, ReportFormat[]> = {
  executive: ["pdf"],
  vulnerability: ["pdf", "json", "docx"],
  "qa-gap": ["pdf", "docx"],
  "test-bundle": ["feature", "py", "ts", "docx"],
  compliance: ["pdf", "csv"],
  diff: ["pdf", "json"],
};

export function ReportsPage() {
  const { id } = useParams<{ id: string }>();
  const [reports, setReports] = useState<Report[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [reportType, setReportType] = useState<ReportType>("executive");
  const [format, setFormat] = useState<ReportFormat>("pdf");
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    if (id) getReports(id).then((r) => setReports(r.data));
  }, [id]);

  useEffect(() => {
    const available = reportFormatOptions[reportType];
    if (!available.includes(format)) setFormat(available[0]);
  }, [reportType]);

  const handleGenerate = async () => {
    if (!id) return;
    setGenerating(true);
    try {
      const { data } = await generateReport(id, reportType, format);
      setReports([data, ...reports]);
      setShowForm(false);
    } catch {
      // error handled silently for MVP
    } finally {
      setGenerating(false);
    }
  };

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
            <FileText className="w-5 h-5 text-accent" /> Reports
          </h1>
          <p className="text-muted text-sm mt-0.5">{reports.length} reports generated</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="refero-btn-primary flex items-center gap-2 px-4 py-2 text-sm"
        >
          <Plus className="w-4 h-4" /> Generate Report
        </button>
      </div>

      {/* Generate Form */}
      {showForm && (
        <div className="bg-surface-1 border border-surface-3 rounded-card p-5 mb-5">
          <h3 className="font-semibold text-fg mb-4 text-sm">New Report</h3>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="refero-label">Report Type</label>
              <select
                value={reportType}
                onChange={(e) => setReportType(e.target.value as ReportType)}
                className="refero-input"
              >
                {(Object.keys(reportTypeLabels) as ReportType[]).map((t) => (
                  <option key={t} value={t}>{reportTypeLabels[t]}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="refero-label">Format</label>
              <select
                value={format}
                onChange={(e) => setFormat(e.target.value as ReportFormat)}
                className="refero-input"
              >
                {reportFormatOptions[reportType].map((f) => (
                  <option key={f} value={f}>{formatLabels[f]}</option>
                ))}
              </select>
            </div>
          </div>
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="refero-btn-primary flex items-center gap-2 px-4 py-2 text-sm"
          >
            {generating ? (
              <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Generating…</>
            ) : (
              <><FileText className="w-3.5 h-3.5" /> Generate</>
            )}
          </button>
        </div>
      )}

      {/* Reports List */}
      <div className="bg-surface-1 border border-surface-3 rounded-card overflow-hidden">
        {reports.length === 0 ? (
          <div className="text-center py-14 text-muted">
            <FileText className="w-8 h-8 mx-auto mb-3 opacity-30" />
            <p className="font-medium text-fg-soft">No reports yet</p>
            <p className="text-sm mt-1">Generate your first report from scan data</p>
          </div>
        ) : (
          <div className="divide-y divide-surface-3">
            {reports.map((r) => (
              <div key={r.id} className="flex items-center gap-4 px-5 py-4">
                <div className="w-9 h-9 rounded-badge bg-accent/10 flex items-center justify-center shrink-0">
                  <FileText className="w-4 h-4 text-accent" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-fg text-sm">{reportTypeLabels[r.report_type]}</p>
                  <p className="text-xs text-muted mt-0.5">
                    {formatLabels[r.format]} · {new Date(r.created_at).toLocaleString()}
                  </p>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-badge font-medium border ${
                  r.status === "ready"
                    ? "bg-emerald-900/20 text-emerald-400 border-emerald-800/40"
                    : r.status === "generating"
                    ? "bg-accent/15 text-accent border-accent/30 animate-pulse"
                    : "bg-red-900/20 text-red-400 border-red-800/40"
                }`}>
                  {r.status}
                </span>
                {r.status === "ready" && r.download_url && (
                  <a
                    href={r.download_url}
                    className="flex items-center gap-1.5 text-accent hover:text-accent-dim text-sm font-medium transition-colors"
                    download
                  >
                    <Download className="w-3.5 h-3.5" /> Download
                  </a>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </Layout>
  );
}
