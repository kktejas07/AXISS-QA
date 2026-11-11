/**
 * AuditPage — Full 5-tier application audit
 *
 * Phase 1 (form): collect URL + optional mobile inputs, start audit
 * Phase 2 (live): SSE-driven progress, tier status badges
 * Phase 3 (results): tabbed tier results, risk score, PDF download
 */
import { useState, useEffect, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Layout } from "../components/Layout";
import {
  createAudit,
  getAudit,
  uploadApk,
  uploadIpa,
  listAudits,
  type AuditJob,
} from "../api/audits";
import {
  Globe,
  Smartphone,
  Shield,
  ClipboardList,
  FileText,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  AlertTriangle,
  Download,
  Plus,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

// ─── Tier meta ──────────────────────────────────────────────────────────────

const TIERS = [
  { key: "tier1", label: "Web QA", icon: Globe, desc: "Playwright crawl + WCAG 2.1 AA + test generation" },
  { key: "tier2", label: "Mobile", icon: Smartphone, desc: "APK / IPA / Store URL analysis + Appium tests" },
  { key: "tier3", label: "Cyber Security", icon: Shield, desc: "BOLA, JWT, CORS, rate limiting, secrets, subdomains" },
  { key: "tier4", label: "Manual QA", icon: ClipboardList, desc: "AI-generated checklists + Jira CSV export" },
  { key: "tier5", label: "Unified Report", icon: FileText, desc: "Claude executive summary + PDF report" },
] as const;

type TierKey = typeof TIERS[number]["key"];

// ─── Status badge ────────────────────────────────────────────────────────────

function TierBadge({ status }: { status: string }) {
  const map: Record<string, { color: string; icon: JSX.Element }> = {
    pending:   { color: "text-gray-400",  icon: <Clock className="w-4 h-4" /> },
    running:   { color: "text-blue-500",  icon: <Loader2 className="w-4 h-4 animate-spin" /> },
    completed: { color: "text-green-500", icon: <CheckCircle2 className="w-4 h-4" /> },
    failed:    { color: "text-red-500",   icon: <XCircle className="w-4 h-4" /> },
    skipped:   { color: "text-yellow-500",icon: <AlertTriangle className="w-4 h-4" /> },
  };
  const s = map[status] ?? map["pending"];
  return (
    <span className={`flex items-center gap-1 text-sm font-medium ${s.color}`}>
      {s.icon}
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

// ─── Risk score ring ─────────────────────────────────────────────────────────

function RiskRing({ score }: { score: number }) {
  const color = score >= 70 ? "#ef4444" : score >= 40 ? "#f59e0b" : "#22c55e";
  const r = 44;
  const circ = 2 * Math.PI * r;
  const dash = circ * (1 - score / 100);
  return (
    <svg width="110" height="110" viewBox="0 0 110 110">
      <circle cx="55" cy="55" r={r} fill="none" stroke="#374151" strokeWidth="10" />
      <circle
        cx="55" cy="55" r={r} fill="none"
        stroke={color} strokeWidth="10"
        strokeDasharray={circ}
        strokeDashoffset={dash}
        strokeLinecap="round"
        transform="rotate(-90 55 55)"
        style={{ transition: "stroke-dashoffset 0.8s ease" }}
      />
      <text x="55" y="60" textAnchor="middle" fill={color} fontSize="22" fontWeight="700">{score}</text>
    </svg>
  );
}

// ─── Collapsible JSON viewer ─────────────────────────────────────────────────

function JsonSection({ title, data }: { title: string; data: unknown }) {
  const [open, setOpen] = useState(false);
  if (!data) return null;
  return (
    <div className="border border-gray-700 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-800 text-sm font-medium text-gray-200 hover:bg-gray-750"
      >
        {title}
        {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>
      {open && (
        <pre className="p-4 text-xs text-gray-300 overflow-auto max-h-96 bg-gray-900">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  );
}

// ─── Tier-1 Web results panel ────────────────────────────────────────────────

function Tier1Panel({ result }: { result: Record<string, unknown> }) {
  const a11y = result.a11y_summary as Record<string, number> | undefined;
  const tests = (result.playwright_tests as string) || "";
  const manual = (result.manual_test_cases as unknown[]) || [];
  const routes = (result.routes_found as string[]) || [];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: "Pages Audited", val: result.pages_audited as number },
          { label: "Routes Found", val: routes.length },
          { label: "A11y Violations", val: a11y?.total_violations ?? 0 },
          { label: "Manual Test Cases", val: manual.length },
        ].map(({ label, val }) => (
          <div key={label} className="bg-gray-800 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-white">{val}</div>
            <div className="text-xs text-gray-400 mt-1">{label}</div>
          </div>
        ))}
      </div>
      {a11y && (
        <div className="text-sm text-gray-300">
          <span className="font-semibold text-white">Accessibility: </span>
          {a11y.critical ?? 0} critical · {a11y.serious ?? 0} serious · {a11y.moderate ?? 0} moderate
        </div>
      )}
      {tests && (
        <div>
          <div className="text-sm font-semibold text-gray-300 mb-1">Generated Playwright Tests</div>
          <pre className="bg-gray-900 rounded p-3 text-xs text-green-400 overflow-auto max-h-72">{tests}</pre>
        </div>
      )}
      <JsonSection title="Routes Found" data={routes} />
      <JsonSection title="Manual Test Cases (JSON)" data={manual} />
    </div>
  );
}

// ─── Tier-2 Mobile results panel ─────────────────────────────────────────────

function Tier2Panel({ result }: { result: Record<string, unknown> }) {
  if (result.skipped) return <p className="text-gray-400 text-sm">{result.skipped as string}</p>;
  const flags = (result.security_flags as string[]) || [];
  const perms = (result.dangerous_permissions as string[]) || [];
  const appiumCode = result.appium_tests as string || result.appium_test_code as string || "";
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {[
          { label: "Platform", val: result.platform as string || "—" },
          { label: "App", val: result.app_name as string || "—" },
          { label: "Security Flags", val: flags.length },
        ].map(({ label, val }) => (
          <div key={label} className="bg-gray-800 rounded-lg p-3">
            <div className="text-xs text-gray-400">{label}</div>
            <div className="text-white font-semibold mt-1">{val}</div>
          </div>
        ))}
      </div>
      {flags.length > 0 && (
        <div>
          <div className="text-sm font-semibold text-red-400 mb-2">Security Flags</div>
          <ul className="space-y-1">
            {flags.map((f, i) => (
              <li key={i} className="text-sm text-red-300 flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />{f}
              </li>
            ))}
          </ul>
        </div>
      )}
      {perms.length > 0 && (
        <JsonSection title={`Dangerous Permissions (${perms.length})`} data={perms} />
      )}
      {appiumCode && (
        <div>
          <div className="text-sm font-semibold text-gray-300 mb-1">Generated Appium Tests</div>
          <pre className="bg-gray-900 rounded p-3 text-xs text-blue-300 overflow-auto max-h-72">{appiumCode}</pre>
        </div>
      )}
    </div>
  );
}

// ─── Tier-3 Cyber security panel ─────────────────────────────────────────────

const SEV_COLOR: Record<string, string> = {
  critical: "bg-red-600 text-white",
  high:     "bg-orange-500 text-white",
  medium:   "bg-yellow-500 text-black",
  low:      "bg-blue-500 text-white",
  info:     "bg-gray-600 text-white",
};

function Tier3Panel({ result }: { result: Record<string, unknown> }) {
  const findings = (result.findings as Array<Record<string, string>>) || [];
  const secrets = (result.js_secrets as unknown[]) || [];
  const subs = (result.subdomains_found as string[]) || [];
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: "Total Findings", val: findings.length },
          { label: "JS Secrets", val: secrets.length },
          { label: "Subdomains", val: subs.length },
          { label: "Endpoints Tested", val: result.endpoints_tested as number || 0 },
        ].map(({ label, val }) => (
          <div key={label} className="bg-gray-800 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-white">{val}</div>
            <div className="text-xs text-gray-400 mt-1">{label}</div>
          </div>
        ))}
      </div>
      <div className="space-y-3">
        {findings.map((f, i) => (
          <div key={i} className="border border-gray-700 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <span className={`text-xs px-2 py-1 rounded font-semibold flex-shrink-0 ${SEV_COLOR[f.severity] || "bg-gray-600 text-white"}`}>
                {(f.severity || "?").toUpperCase()}
              </span>
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-white text-sm">{f.title}</div>
                <div className="text-xs text-gray-400 mt-1">{f.description}</div>
                {f.remediation && (
                  <div className="text-xs text-green-400 mt-2">
                    <span className="font-semibold">Fix: </span>{f.remediation}
                  </div>
                )}
                {f.cwe_id && (
                  <div className="text-xs text-gray-500 mt-1">{f.cwe_id} · {f.owasp_category}</div>
                )}
              </div>
            </div>
          </div>
        ))}
        {findings.length === 0 && (
          <p className="text-sm text-green-400 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" /> No security findings detected
          </p>
        )}
      </div>
      {subs.length > 0 && <JsonSection title={`Subdomains Found (${subs.length})`} data={subs} />}
      {secrets.length > 0 && <JsonSection title={`JS Secrets Found (${secrets.length})`} data={secrets} />}
    </div>
  );
}

// ─── Tier-4 Manual QA panel ──────────────────────────────────────────────────

function Tier4Panel({ result }: { result: Record<string, unknown> }) {
  const cases = (result.test_cases as Array<Record<string, unknown>>) || [];
  const csv = result.jira_csv as string | null;
  const downloadCsv = () => {
    if (!csv) return;
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "manual_test_cases.csv"; a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-sm text-gray-300">{cases.length} test cases generated</div>
        {csv && (
          <button
            onClick={downloadCsv}
            className="flex items-center gap-2 text-sm bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg"
          >
            <Download className="w-4 h-4" /> Export Jira CSV
          </button>
        )}
      </div>
      <div className="space-y-3">
        {cases.slice(0, 20).map((tc, i) => (
          <div key={i} className="border border-gray-700 rounded-lg p-3">
            <div className="flex items-start gap-2">
              <span className="text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded flex-shrink-0">
                {tc.priority as string || "medium"}
              </span>
              <div>
                <div className="text-sm font-medium text-white">{tc.title as string}</div>
                <div className="text-xs text-gray-400 mt-1">{tc.category as string}</div>
                {Array.isArray(tc.steps) && tc.steps.length > 0 && (
                  <ol className="text-xs text-gray-400 mt-2 space-y-0.5 list-decimal list-inside">
                    {(tc.steps as string[]).slice(0, 4).map((s, j) => (
                      <li key={j}>{s}</li>
                    ))}
                  </ol>
                )}
              </div>
            </div>
          </div>
        ))}
        {cases.length > 20 && (
          <p className="text-xs text-gray-500 text-center">+{cases.length - 20} more (export CSV for full list)</p>
        )}
      </div>
    </div>
  );
}

// ─── Tier-5 Report panel ─────────────────────────────────────────────────────

function Tier5Panel({ result, auditId }: { result: Record<string, unknown>; auditId: string }) {
  const summary = result.executive_summary as string || "";
  const handleDownload = () => {
    const apiBase = (import.meta.env.VITE_API_URL || "").replace("/api/v1", "");
    window.open(`${apiBase}/api/v1/audits/${auditId}/download`, "_blank");
  };
  return (
    <div className="space-y-4">
      {summary && (
        <div className="bg-gray-800 rounded-lg p-4">
          <div className="text-sm font-semibold text-gray-300 mb-3">Executive Summary</div>
          <div className="text-sm text-gray-200 whitespace-pre-wrap leading-relaxed">{summary}</div>
        </div>
      )}
      <button
        onClick={handleDownload}
        className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm px-4 py-2 rounded-lg"
      >
        <Download className="w-4 h-4" /> Download Full PDF Report
      </button>
    </div>
  );
}

// ─── NEW AUDIT FORM ───────────────────────────────────────────────────────────

function NewAuditForm({ onCreated }: { onCreated: (id: string) => void }) {
  const [url, setUrl] = useState("");
  const [appName, setAppName] = useState("");
  const [mobileUrl, setMobileUrl] = useState("");
  const [showMobile, setShowMobile] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleStart = async () => {
    if (!url.trim()) { setError("Target URL is required"); return; }
    setError("");
    setLoading(true);
    try {
      const { data } = await createAudit({
        target_url: url.trim(),
        app_name: appName.trim() || undefined,
        mobile_url: mobileUrl.trim() || undefined,
      });
      onCreated(data.id);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err?.response?.data?.detail || "Failed to start audit");
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="text-center">
        <h1 className="text-2xl font-bold text-white">Full Application Audit</h1>
        <p className="text-gray-400 mt-2 text-sm">
          5-tier audit: Web QA · Mobile · Cyber Security · Manual QA · Unified Report
        </p>
      </div>

      {/* Tier overview */}
      <div className="grid grid-cols-5 gap-2">
        {TIERS.map(({ key, label, icon: Icon }) => (
          <div key={key} className="flex flex-col items-center bg-gray-800 rounded-lg p-3 gap-2">
            <Icon className="w-5 h-5 text-indigo-400" />
            <span className="text-xs text-gray-300 text-center leading-tight">{label}</span>
          </div>
        ))}
      </div>

      <div className="bg-gray-800 rounded-xl p-6 space-y-5">
        <div>
          <label className="text-sm text-gray-300 font-medium block mb-1">Target URL *</label>
          <input
            type="url"
            value={url}
            onChange={e => setUrl(e.target.value)}
            placeholder="https://example.com"
            className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div>
          <label className="text-sm text-gray-300 font-medium block mb-1">App Name (optional)</label>
          <input
            value={appName}
            onChange={e => setAppName(e.target.value)}
            placeholder="My App"
            className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        <button
          type="button"
          onClick={() => setShowMobile(o => !o)}
          className="text-sm text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
        >
          <Smartphone className="w-4 h-4" />
          {showMobile ? "Hide" : "Add"} mobile inputs (optional)
        </button>

        {showMobile && (
          <div>
            <label className="text-sm text-gray-300 font-medium block mb-1">
              Play Store / App Store URL
            </label>
            <input
              value={mobileUrl}
              onChange={e => setMobileUrl(e.target.value)}
              placeholder="https://play.google.com/store/apps/details?id=com.example"
              className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <p className="text-xs text-gray-500 mt-1">
              You can also upload APK/IPA files after the audit starts.
            </p>
          </div>
        )}

        {error && <p className="text-red-400 text-sm">{error}</p>}

        <button
          onClick={handleStart}
          disabled={loading}
          className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-semibold py-3 rounded-lg transition-colors"
        >
          {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Globe className="w-5 h-5" />}
          {loading ? "Starting Audit…" : "Start Full Audit"}
        </button>
      </div>
    </div>
  );
}

// ─── AUDIT DETAIL (live + results) ───────────────────────────────────────────

function AuditDetail({ auditId }: { auditId: string }) {
  const [job, setJob] = useState<AuditJob | null>(null);
  const [activeTab, setActiveTab] = useState<TierKey>("tier1");
  const [apkFile, setApkFile] = useState<File | null>(null);
  const [ipaFile, setIpaFile] = useState<File | null>(null);
  const [uploadMsg, setUploadMsg] = useState("");
  const evtRef = useRef<EventSource | null>(null);

  // initial load
  useEffect(() => {
    getAudit(auditId).then(r => setJob(r.data)).catch(console.error);
  }, [auditId]);

  // SSE stream while running
  useEffect(() => {
    if (!job) return;
    const terminal = ["completed", "failed", "partial"];
    if (terminal.includes(job.status)) return;

    const apiBase = (import.meta.env.VITE_API_URL || "").replace("/api/v1", "");
    const token = localStorage.getItem("token") || "";
    const src = new EventSource(
      `${apiBase}/api/v1/audits/${auditId}/stream?token=${encodeURIComponent(token)}`
    );
    evtRef.current = src;

    src.addEventListener("progress", () => {
      getAudit(auditId).then(r => setJob(r.data)).catch(console.error);
    });
    src.addEventListener("done", () => {
      getAudit(auditId).then(r => setJob(r.data)).catch(console.error);
      src.close();
    });
    src.onerror = () => src.close();

    return () => { src.close(); };
  }, [auditId, job?.status]);

  const handleUploadApk = async () => {
    if (!apkFile || !job) return;
    setUploadMsg("Uploading APK…");
    try {
      const { data } = await uploadApk(job.id, apkFile);
      setJob(data);
      setUploadMsg("APK uploaded ✓");
    } catch { setUploadMsg("Upload failed"); }
  };

  const handleUploadIpa = async () => {
    if (!ipaFile || !job) return;
    setUploadMsg("Uploading IPA…");
    try {
      const { data } = await uploadIpa(job.id, ipaFile);
      setJob(data);
      setUploadMsg("IPA uploaded ✓");
    } catch { setUploadMsg("Upload failed"); }
  };

  if (!job) return (
    <div className="flex justify-center py-16">
      <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
    </div>
  );

  const isRunning = ["queued", "running"].includes(job.status);
  const isDone = ["completed", "partial"].includes(job.status);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gray-800 rounded-xl p-5">
        <div className="flex flex-col md:flex-row md:items-start gap-4">
          <div className="flex-1">
            <h2 className="text-lg font-bold text-white break-all">{job.target_url}</h2>
            {job.app_name && <p className="text-gray-400 text-sm mt-1">{job.app_name}</p>}
            <div className="flex items-center gap-3 mt-3">
              <TierBadge status={job.status} />
              <span className="text-sm text-gray-400">{job.progress}% complete</span>
            </div>
          </div>
          {isDone && job.risk_score !== null && (
            <div className="flex flex-col items-center gap-1">
              <RiskRing score={job.risk_score} />
              <span className="text-xs text-gray-400">Risk Score</span>
            </div>
          )}
        </div>

        {/* Progress bar */}
        <div className="mt-4 bg-gray-700 rounded-full h-2 overflow-hidden">
          <div
            className="h-full bg-indigo-500 rounded-full transition-all duration-500"
            style={{ width: `${job.progress}%` }}
          />
        </div>

        {/* Summary stats */}
        {isDone && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
            {[
              { label: "Critical", val: job.critical_count, color: "text-red-400" },
              { label: "High", val: job.high_count, color: "text-orange-400" },
              { label: "Pages Audited", val: job.total_pages_audited, color: "text-blue-400" },
              { label: "Test Cases", val: job.total_test_cases, color: "text-green-400" },
            ].map(({ label, val, color }) => (
              <div key={label} className="bg-gray-900 rounded-lg p-3 text-center">
                <div className={`text-xl font-bold ${color}`}>{val}</div>
                <div className="text-xs text-gray-500 mt-0.5">{label}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Tier status strip */}
      <div className="grid grid-cols-5 gap-2">
        {TIERS.map(({ key, label, icon: Icon }) => {
          const status = job[`${key}_status` as keyof AuditJob] as string;
          return (
            <div
              key={key}
              className="bg-gray-800 rounded-lg p-3 flex flex-col items-center gap-1 cursor-pointer hover:bg-gray-750"
              onClick={() => setActiveTab(key)}
            >
              <Icon className={`w-5 h-5 ${activeTab === key ? "text-indigo-400" : "text-gray-500"}`} />
              <span className="text-xs text-gray-300 text-center">{label}</span>
              <TierBadge status={status} />
            </div>
          );
        })}
      </div>

      {/* APK/IPA upload (always visible) */}
      <div className="bg-gray-800 rounded-xl p-4">
        <div className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
          <Smartphone className="w-4 h-4" /> Upload Mobile App (optional)
        </div>
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="flex items-center gap-2 flex-1">
            <input type="file" accept=".apk" onChange={e => setApkFile(e.target.files?.[0] || null)}
              className="text-xs text-gray-400 file:mr-2 file:text-xs file:bg-gray-700 file:border-0 file:text-gray-300 file:rounded file:px-2 file:py-1" />
            <button onClick={handleUploadApk} disabled={!apkFile}
              className="text-xs bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white px-3 py-1.5 rounded">
              Upload APK
            </button>
          </div>
          <div className="flex items-center gap-2 flex-1">
            <input type="file" accept=".ipa" onChange={e => setIpaFile(e.target.files?.[0] || null)}
              className="text-xs text-gray-400 file:mr-2 file:text-xs file:bg-gray-700 file:border-0 file:text-gray-300 file:rounded file:px-2 file:py-1" />
            <button onClick={handleUploadIpa} disabled={!ipaFile}
              className="text-xs bg-purple-600 hover:bg-purple-700 disabled:opacity-40 text-white px-3 py-1.5 rounded">
              Upload IPA
            </button>
          </div>
        </div>
        {uploadMsg && <p className="text-xs text-green-400 mt-2">{uploadMsg}</p>}
      </div>

      {/* Running message */}
      {isRunning && (
        <div className="text-center py-6">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mx-auto mb-3" />
          <p className="text-gray-400 text-sm">Audit in progress — results will appear here as each tier completes.</p>
        </div>
      )}

      {/* Tier results tabs */}
      {isDone && (
        <div className="bg-gray-800 rounded-xl overflow-hidden">
          <div className="flex border-b border-gray-700 overflow-x-auto">
            {TIERS.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                className={`px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors ${
                  activeTab === key
                    ? "text-white border-b-2 border-indigo-500 bg-gray-750"
                    : "text-gray-400 hover:text-gray-200"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="p-5">
            {activeTab === "tier1" && job.tier1_result && <Tier1Panel result={job.tier1_result as Record<string, unknown>} />}
            {activeTab === "tier2" && job.tier2_result && <Tier2Panel result={job.tier2_result as Record<string, unknown>} />}
            {activeTab === "tier3" && job.tier3_result && <Tier3Panel result={job.tier3_result as Record<string, unknown>} />}
            {activeTab === "tier4" && job.tier4_result && <Tier4Panel result={job.tier4_result as Record<string, unknown>} />}
            {activeTab === "tier5" && job.tier5_result && <Tier5Panel result={job.tier5_result as Record<string, unknown>} auditId={job.id} />}
            {!job[`${activeTab}_result` as keyof AuditJob] && (
              <p className="text-sm text-gray-500 text-center py-6">No results for this tier yet.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── AUDIT LIST ───────────────────────────────────────────────────────────────

function AuditList({ onSelect, onNew }: { onSelect: (id: string) => void; onNew: () => void }) {
  const [audits, setAudits] = useState<AuditJob[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listAudits().then(r => { setAudits(r.data); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-white">Audit History</h2>
        <button
          onClick={onNew}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm px-4 py-2 rounded-lg"
        >
          <Plus className="w-4 h-4" /> New Audit
        </button>
      </div>
      {loading && <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-indigo-500" /></div>}
      {!loading && audits.length === 0 && (
        <div className="text-center py-16 text-gray-500">
          No audits yet. Start your first full application audit!
        </div>
      )}
      <div className="space-y-3">
        {audits.map(a => (
          <div
            key={a.id}
            onClick={() => onSelect(a.id)}
            className="bg-gray-800 rounded-xl p-4 cursor-pointer hover:bg-gray-750 transition-colors"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="font-medium text-white text-sm truncate">{a.target_url}</div>
                {a.app_name && <div className="text-xs text-gray-400">{a.app_name}</div>}
                <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                  <span>{new Date(a.created_at).toLocaleDateString()}</span>
                  <span>{a.total_pages_audited} pages · {a.critical_count} critical</span>
                </div>
              </div>
              <div className="flex flex-col items-end gap-2">
                <TierBadge status={a.status} />
                {a.risk_score !== null && (
                  <span className={`text-xs font-bold ${a.risk_score >= 70 ? "text-red-400" : a.risk_score >= 40 ? "text-yellow-400" : "text-green-400"}`}>
                    Risk: {a.risk_score}/100
                  </span>
                )}
              </div>
            </div>
            <div className="mt-3 bg-gray-700 rounded-full h-1.5 overflow-hidden">
              <div className="h-full bg-indigo-500 rounded-full" style={{ width: `${a.progress}%` }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── MAIN PAGE ────────────────────────────────────────────────────────────────

type View = "list" | "new" | "detail";

export function AuditPage() {
  const { auditId } = useParams<{ auditId?: string }>();
  const navigate = useNavigate();
  const [view, setView] = useState<View>(auditId ? "detail" : "list");
  const [currentAuditId, setCurrentAuditId] = useState<string | null>(auditId || null);

  const handleCreated = (id: string) => {
    setCurrentAuditId(id);
    setView("detail");
    navigate(`/audits/${id}`, { replace: true });
  };

  const handleSelect = (id: string) => {
    setCurrentAuditId(id);
    setView("detail");
    navigate(`/audits/${id}`);
  };

  return (
    <Layout>
      <div className="max-w-4xl mx-auto px-4 py-6">
        {view === "list" && (
          <AuditList onSelect={handleSelect} onNew={() => setView("new")} />
        )}
        {view === "new" && (
          <div>
            <button
              onClick={() => setView("list")}
              className="text-sm text-gray-400 hover:text-gray-200 mb-4 flex items-center gap-1"
            >
              ← Back to audits
            </button>
            <NewAuditForm onCreated={handleCreated} />
          </div>
        )}
        {view === "detail" && currentAuditId && (
          <div>
            <button
              onClick={() => { setView("list"); navigate("/audits"); }}
              className="text-sm text-gray-400 hover:text-gray-200 mb-4 flex items-center gap-1"
            >
              ← Back to audits
            </button>
            <AuditDetail auditId={currentAuditId} />
          </div>
        )}
      </div>
    </Layout>
  );
}
