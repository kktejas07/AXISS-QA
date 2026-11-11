import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Layout } from "../components/Layout";
import { SeverityBadge } from "../components/SeverityBadge";
import { getVulnerabilities } from "../api/scans";
import type { Vulnerability, Severity } from "../types";
import { ArrowLeft, ChevronDown, ChevronUp, SlidersHorizontal } from "lucide-react";

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
    <Layout>
      <Link
        to={`/scans/${id}`}
        className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-accent transition-colors mb-5"
      >
        <ArrowLeft className="w-3.5 h-3.5" /> Back to Scan Results
      </Link>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-fg">Vulnerabilities</h1>
          <p className="text-muted text-sm mt-0.5">{vulns.length} findings detected</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 mb-5 bg-surface-1 border border-surface-3 rounded-card p-3">
        <SlidersHorizontal className="w-4 h-4 text-muted-dim shrink-0" />
        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value as Severity | "all")}
          className="text-sm bg-surface-2 border border-surface-3 text-fg rounded-badge px-3 py-1.5 focus:outline-none focus:border-accent"
        >
          <option value="all">All Severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
          <option value="informational">Informational</option>
        </select>
        <select
          value={owaspFilter}
          onChange={(e) => setOwaspFilter(e.target.value)}
          className="text-sm bg-surface-2 border border-surface-3 text-fg rounded-badge px-3 py-1.5 focus:outline-none focus:border-accent"
        >
          {owaspCategories.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <span className="text-xs text-muted-dim ml-auto">{filtered.length} results</span>
      </div>

      {/* Table */}
      <div className="bg-surface-1 border border-surface-3 rounded-card overflow-hidden">
        {filtered.length === 0 ? (
          <div className="text-center py-14 text-muted">
            <p className="font-medium text-fg-soft">No vulnerabilities found</p>
            <p className="text-sm mt-1">Adjust your filters or this scan found no issues</p>
          </div>
        ) : (
          <div className="divide-y divide-surface-3">
            {filtered.map((v) => (
              <div key={v.id}>
                <button
                  onClick={() => setExpandedId(expandedId === v.id ? null : v.id)}
                  className="w-full flex items-center gap-4 px-5 py-4 text-left hover:bg-surface-2 transition-colors"
                >
                  <SeverityBadge severity={v.severity} />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-fg text-sm">{v.title}</p>
                    <p className="text-xs text-muted truncate font-mono mt-0.5">{v.affected_url}</p>
                  </div>
                  <span className="text-xs text-muted-dim shrink-0">{v.owasp_category}</span>
                  {v.cvss_score != null && (
                    <span className="text-xs font-mono text-muted shrink-0">CVSS {v.cvss_score}</span>
                  )}
                  <span
                    className={`text-xs px-2 py-0.5 rounded-badge font-medium border shrink-0 ${
                      v.status === "open"
                        ? "bg-red-900/20 text-red-400 border-red-800/40"
                        : v.status === "fixed"
                        ? "bg-emerald-900/20 text-emerald-400 border-emerald-800/40"
                        : "bg-surface-2 text-muted border-surface-3"
                    }`}
                  >
                    {v.status}
                  </span>
                  {expandedId === v.id ? (
                    <ChevronUp className="w-4 h-4 text-muted-dim shrink-0" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-muted-dim shrink-0" />
                  )}
                </button>
                {expandedId === v.id && (
                  <div className="px-5 pb-5 bg-surface-2 border-t border-surface-3">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                      <div>
                        <h4 className="text-xs font-semibold text-muted uppercase tracking-wider mb-2">
                          Description
                        </h4>
                        <p className="text-sm text-fg-soft">{v.description}</p>
                      </div>
                      <div>
                        <h4 className="text-xs font-semibold text-muted uppercase tracking-wider mb-2">
                          Remediation
                        </h4>
                        <p className="text-sm text-fg-soft">{v.remediation}</p>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-4 mt-4">
                      {v.cwe_id && (
                        <div className="text-xs text-muted">
                          CWE: <span className="font-mono text-fg-soft">{v.cwe_id}</span>
                        </div>
                      )}
                      {v.cve_id && (
                        <div className="text-xs text-muted">
                          CVE: <span className="font-mono text-fg-soft">{v.cve_id}</span>
                        </div>
                      )}
                      {v.affected_parameter && (
                        <div className="text-xs text-muted">
                          Parameter: <span className="font-mono text-fg-soft">{v.affected_parameter}</span>
                        </div>
                      )}
                      <div className="text-xs text-muted">
                        Fix Effort: <span className="text-fg-soft">{v.fix_effort}</span>
                      </div>
                    </div>
                    {(v.proof_request || v.proof_response) && (
                      <div className="mt-4 space-y-3">
                        {v.proof_request && (
                          <div>
                            <h4 className="text-xs font-semibold text-muted uppercase tracking-wider mb-1.5">
                              Proof — Request
                            </h4>
                            <pre className="bg-app border border-surface-3 text-emerald-400 text-xs p-3 rounded-card overflow-x-auto font-mono">
                              {v.proof_request}
                            </pre>
                          </div>
                        )}
                        {v.proof_response && (
                          <div>
                            <h4 className="text-xs font-semibold text-muted uppercase tracking-wider mb-1.5">
                              Proof — Response
                            </h4>
                            <pre className="bg-app border border-surface-3 text-emerald-400 text-xs p-3 rounded-card overflow-x-auto font-mono">
                              {v.proof_response}
                            </pre>
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
    </Layout>
  );
}
