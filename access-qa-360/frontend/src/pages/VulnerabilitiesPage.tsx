import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { QuickScanShell } from "../components/QuickScanShell";
import { SeverityBadge } from "../components/SeverityBadge";
import { getVulnerabilities } from "../api/scans";
import type { Vulnerability, Severity } from "../types";
import { ArrowLeft, ChevronDown, ChevronUp, Filter } from "lucide-react";

const owaspCategories = [
  "All",
  "Injection",
  "Broken Authentication",
  "Sensitive Data Exposure",
  "XXE",
  "Broken Access Control",
  "Security Misconfiguration",
  "XSS",
  "Insecure Deserialization",
  "Known Vulnerabilities",
  "Insufficient Logging",
  "SSRF",
  "CSRF",
  "Open Redirect",
  "Clickjacking",
];

export function VulnerabilitiesPage() {
  const { id } = useParams<{ id: string }>();
  const [vulns, setVulns] = useState<Vulnerability[]>([]);
  const [severityFilter, setSeverityFilter] = useState<Severity | "all">("all");
  const [owaspFilter, setOwaspFilter] = useState("All");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    if (id) getVulnerabilities(id).then((r) => setVulns(r.data));
  }, [id]);

  const filtered = vulns.filter((v) => {
    if (severityFilter !== "all" && v.severity !== severityFilter) return false;
    if (owaspFilter !== "All" && v.owasp_category !== owaspFilter) return false;
    return true;
  });

  return (
    <QuickScanShell id={id} tab="vulns">


      {/* Filters */}
      <div className="mb-6 flex flex-wrap items-center gap-3 rounded-2xl border border-gray-300 bg-white p-3">
        <Filter className="w-4 h-4 text-body" />
        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value as Severity | "all")}
          className="h-11 min-w-0 max-w-full rounded-[10px] border border-gray-400 bg-white px-2.5 text-[15px]"
        >
          <option value="all">All severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
          <option value="informational">Informational</option>
        </select>
        <select
          value={owaspFilter}
          onChange={(e) => setOwaspFilter(e.target.value)}
          className="h-11 min-w-0 max-w-full rounded-[10px] border border-gray-400 bg-white px-2.5 text-[15px]"
        >
          {owaspCategories.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <span className="text-xs text-body ml-auto">{filtered.length} results</span>
      </div>

      {/* Table */}
      <div className="bg-white border border-gray-300 rounded-2xl overflow-hidden">
        {filtered.length === 0 ? (
          <div className="text-center py-12 text-body">
            <p className="font-medium">No vulnerabilities found</p>
            <p className="text-sm mt-1">Adjust your filters or this scan found no issues</p>
          </div>
        ) : (
          <div className="divide-y divide-line">
            {filtered.map((v) => (
              <div key={v.id}>
                <button
                  onClick={() => setExpandedId(expandedId === v.id ? null : v.id)}
                  className="w-full flex items-center gap-4 px-5 py-4 text-left hover:bg-soft transition"
                >
                  <SeverityBadge severity={v.severity} />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-ink text-sm">{v.title}</p>
                    <p className="text-xs text-body truncate font-mono">{v.affected_url}</p>
                  </div>
                  <span className="text-xs text-body shrink-0">{v.owasp_category}</span>
                  {v.cvss_score != null && (
                    <span className="text-xs font-mono text-body shrink-0">CVSS {v.cvss_score}</span>
                  )}
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                    v.status === "open" ? "bg-red-50 text-red-600" :
                    v.status === "fixed" ? "bg-emerald-50 text-emerald-600" :
                    "bg-gray-100 text-body"
                  }`}>
                    {v.status}
                  </span>
                  {expandedId === v.id ? <ChevronUp className="w-4 h-4 text-body" /> : <ChevronDown className="w-4 h-4 text-body" />}
                </button>
                {expandedId === v.id && (
                  <div className="px-5 pb-5 bg-soft border-t border-gray-300">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                      <div>
                        <h4 className="text-xs font-semibold text-body uppercase mb-2">Description</h4>
                        <p className="text-sm text-ink">{v.description}</p>
                      </div>
                      <div>
                        <h4 className="text-xs font-semibold text-body uppercase mb-2">Remediation</h4>
                        <p className="text-sm text-ink">{v.remediation}</p>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
                      {v.cwe_id && (
                        <div className="text-xs"><span className="text-body">CWE:</span> <span className="font-mono">{v.cwe_id}</span></div>
                      )}
                      {v.cve_id && (
                        <div className="text-xs"><span className="text-body">CVE:</span> <span className="font-mono">{v.cve_id}</span></div>
                      )}
                      {v.affected_parameter && (
                        <div className="text-xs"><span className="text-body">Parameter:</span> <span className="font-mono">{v.affected_parameter}</span></div>
                      )}
                      <div className="text-xs"><span className="text-body">Fix Effort:</span> {v.fix_effort}</div>
                    </div>
                    {(v.proof_request || v.proof_response) && (
                      <div className="mt-4 space-y-3">
                        {v.proof_request && (
                          <div>
                            <h4 className="text-xs font-semibold text-body uppercase mb-1">Proof — Request</h4>
                            <pre className="bg-ink text-gray-100 text-xs p-3 rounded-lg overflow-x-auto font-mono">{v.proof_request}</pre>
                          </div>
                        )}
                        {v.proof_response && (
                          <div>
                            <h4 className="text-xs font-semibold text-body uppercase mb-1">Proof — Response</h4>
                            <pre className="bg-ink text-gray-100 text-xs p-3 rounded-lg overflow-x-auto font-mono">{v.proof_response}</pre>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </QuickScanShell>
  );
}
