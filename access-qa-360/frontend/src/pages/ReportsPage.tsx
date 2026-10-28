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
      <Link to={`/scans/${id}`} className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-indigo-600 mb-4">
        <ArrowLeft className="w-4 h-4" /> Back to Scan Results
      </Link>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-brand-900 flex items-center gap-2">
            <FileText className="w-6 h-6 text-indigo-500" /> Reports
          </h1>
          <p className="text-gray-500 text-sm mt-1">{reports.length} reports generated</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-4 py-2 rounded-lg transition"
        >
          <Plus className="w-4 h-4" /> Generate Report
        </button>
      </div>

      {/* Generate Form */}
      {showForm && (
        <div className="bg-white border border-indigo-200 rounded-xl p-5 mb-6">
          <h3 className="font-semibold text-brand-900 mb-4">New Report</h3>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Report Type</label>
              <select
                value={reportType}
                onChange={(e) => setReportType(e.target.value as ReportType)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white"
              >
                {(Object.keys(reportTypeLabels) as ReportType[]).map((t) => (
                  <option key={t} value={t}>{reportTypeLabels[t]}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Format</label>
              <select
                value={format}
                onChange={(e) => setFormat(e.target.value as ReportFormat)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white"
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
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300 text-white text-sm font-semibold px-4 py-2 rounded-lg transition"
          >
            {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
            Generate
          </button>
        </div>
      )}

      {/* Reports List */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        {reports.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <FileText className="w-10 h-10 mx-auto mb-3 opacity-40" />
            <p className="font-medium">No reports yet</p>
            <p className="text-sm mt-1">Generate your first report from scan data</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {reports.map((r) => (
              <div key={r.id} className="flex items-center gap-4 px-5 py-4">
                <FileText className="w-8 h-8 text-indigo-400 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-brand-900 text-sm">{reportTypeLabels[r.report_type]}</p>
                  <p className="text-xs text-gray-500">
                    {formatLabels[r.format]} &middot; {new Date(r.created_at).toLocaleString()}
                  </p>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                  r.status === "ready" ? "bg-emerald-100 text-emerald-700" :
                  r.status === "generating" ? "bg-indigo-100 text-indigo-700 animate-pulse" :
                  "bg-red-100 text-red-700"
                }`}>
                  {r.status}
                </span>
                {r.status === "ready" && r.download_url && (
                  <a
                    href={r.download_url}
                    className="flex items-center gap-1 text-indigo-600 hover:text-indigo-800 text-sm font-medium"
                    download
                  >
                    <Download className="w-4 h-4" /> Download
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
