import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { QuickScanShell } from "../components/QuickScanShell";
import { getReports, generateReport } from "../api/scans";
import type { Report, ReportType, ReportFormat } from "../types";
import { ArrowLeft, FileText, Download, Loader2, Plus } from "lucide-react";
import { downloadFromApi } from "../utils/download";
import { apiError } from "../utils/errors";

// Only what the server can actually build.
const reportTypeLabels: Record<ReportType, string> = {
  executive_summary: "Executive Summary",
  vulnerability: "Vulnerability Report",
  qa_gap: "QA Gap Report",
  compliance: "Compliance Report",
};

const formatLabels: Record<ReportFormat, string> = {
  pdf: "PDF",
  json: "JSON",
  csv: "CSV",
};

const reportFormatOptions: Record<ReportType, ReportFormat[]> = {
  executive_summary: ["pdf"],
  vulnerability: ["pdf", "json", "csv"],
  qa_gap: ["pdf", "json"],
  compliance: ["pdf", "json"],
};

export function ReportsPage() {
  const { id } = useParams<{ id: string }>();
  const [reports, setReports] = useState<Report[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [reportType, setReportType] = useState<ReportType>("executive_summary");
  const [format, setFormat] = useState<ReportFormat>("pdf");
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (id) getReports(id).then((r) => setReports(r.data)).catch(() => setError("Reports could not be loaded."));
  }, [id]);

  // A report is built in the background, so keep checking until none is still "generating".
  const waiting = reports.some((r) => r.status === "generating");
  useEffect(() => {
    if (!id || !waiting) return;
    const timer = setInterval(() => getReports(id).then((r) => setReports(r.data)).catch(() => {}), 3000);
    return () => clearInterval(timer);
  }, [id, waiting]);

  const download = async (r: Report) => {
    if (!r.download_url) return;
    setError("");
    try {
      await downloadFromApi(r.download_url, `report.${r.format}`);
    } catch {
      setError("The download failed. Try again.");
    }
  };

  useEffect(() => {
    const available = reportFormatOptions[reportType];
    if (!available.includes(format)) setFormat(available[0]);
  }, [reportType]);

  const handleGenerate = async () => {
    if (!id) return;
    setGenerating(true);
    setError("");
    try {
      const { data } = await generateReport(id, reportType, format);
      setReports([data, ...reports]);
      setShowForm(false);
    } catch (e) {
      setError(apiError(e, "The report could not be started. Try again."));
    } finally {
      setGenerating(false);
    }
  };

  return (
    <QuickScanShell id={id} tab="reports">

      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <p className="text-body">{reports.length === 1 ? "1 report" : `${reports.length} reports`}</p>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex h-11 items-center gap-2 rounded-[10px] bg-brand-600 px-4 text-sm font-bold text-white hover:bg-brand-700 disabled:opacity-60"
        >
          <Plus className="w-4 h-4" aria-hidden="true" /> New report
        </button>
      </div>

      {error && (
        <p role="alert" className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>
      )}

      {/* Generate Form */}
      {showForm && (
        <div className="bg-white border border-brand-600 rounded-2xl p-5 mb-6">
          <h3 className="font-semibold text-ink mb-4">New report</h3>
          <div className="mb-4 grid gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-sm font-medium text-ink mb-1">Report type</label>
              <select
                value={reportType}
                onChange={(e) => setReportType(e.target.value as ReportType)}
                className="h-12 w-full rounded-[10px] border border-gray-400 bg-white px-2.5 text-[15px]"
              >
                {(Object.keys(reportTypeLabels) as ReportType[]).map((t) => (
                  <option key={t} value={t}>{reportTypeLabels[t]}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-ink mb-1">Format</label>
              <select
                value={format}
                onChange={(e) => setFormat(e.target.value as ReportFormat)}
                className="h-12 w-full rounded-[10px] border border-gray-400 bg-white px-2.5 text-[15px]"
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
            className="flex h-11 items-center gap-2 rounded-[10px] bg-brand-600 px-4 text-sm font-bold text-white hover:bg-brand-700 disabled:opacity-60"
          >
            {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
            Create report
          </button>
        </div>
      )}

      {/* Reports List */}
      <div className="bg-white border border-gray-300 rounded-2xl overflow-hidden">
        {reports.length === 0 ? (
          <div className="text-center py-12 text-body">
            <FileText className="w-10 h-10 mx-auto mb-3 opacity-40" />
            <p className="font-medium">No reports yet</p>
            <p className="text-sm mt-1">Choose New report to create a PDF, JSON or CSV from this scan.</p>
          </div>
        ) : (
          <div className="divide-y divide-line">
            {reports.map((r) => (
              <div key={r.id} className="flex items-center gap-4 px-5 py-4">
                <FileText className="w-8 h-8 text-brand-600 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-ink text-sm">{reportTypeLabels[r.report_type] ?? r.report_type}</p>
                  <p className="text-xs text-body">
                    {formatLabels[r.format]}, {new Date(r.created_at).toLocaleString()}
                  </p>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                  r.status === "ready" ? "bg-emerald-100 text-emerald-700" :
                  r.status === "generating" ? "bg-brand-50 text-brand-700 animate-pulse" :
                  "bg-red-100 text-red-700"
                }`}>
                  {r.status}
                </span>
                {r.status === "ready" && r.download_url && (
                  <button
                    type="button"
                    onClick={() => download(r)}
                    className="flex items-center gap-1 text-brand-600 hover:text-indigo-800 text-sm font-medium"
                  >
                    <Download className="w-4 h-4" /> Download
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </QuickScanShell>
  );
}
