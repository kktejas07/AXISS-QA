import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { QuickScanShell } from "../components/QuickScanShell";
import { getVulnerabilities } from "../api/scans";
import type { Scan, Severity, Vulnerability } from "../types";
import { card } from "../components/ui";

function Stat({ label, value, note, bad }: { label: string; value: string | number; note: string; bad?: boolean }) {
  return (
    <div className="flex flex-col gap-1 border-b border-line px-6 py-5 last:border-b-0 sm:border-b-0 sm:border-r sm:last:border-r-0">
      <dt className="text-sm font-semibold text-body">{label}</dt>
      <dd className={`text-[40px] font-extrabold leading-tight ${bad ? "text-red-700" : ""}`}>{value}</dd>
      <span className="text-[13.5px] text-body">{note}</span>
    </div>
  );
}

const levels: [Severity, string, string][] = [
  ["critical", "Critical", "bg-red-700"],
  ["high", "High", "bg-orange-500"],
  ["medium", "Medium", "bg-yellow-500"],
  ["low", "Low", "bg-gray-500"],
  ["informational", "Informational", "bg-gray-300"],
];

/** Overview of a quick security scan. */
export function ScanResultsPage() {
  const { id } = useParams<{ id: string }>();
  const [scan, setScan] = useState<Scan | null>(null);
  const [vulns, setVulns] = useState<Vulnerability[]>([]);
  const finished = scan?.status === "completed";

  useEffect(() => {
    if (id && finished) getVulnerabilities(id).then((r) => setVulns(r.data)).catch(() => {});
  }, [id, finished]);

  const total = scan?.vulnerability_count ?? 0;
  const critical = scan?.critical_count ?? 0;

  return (
    <QuickScanShell id={id} tab="overview" onScan={setScan}>
      {!scan ? (
        <LoadingSpinner />
      ) : scan.status === "failed" ? (
        <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-red-800">
          This scan could not finish. Check the address is reachable, then run it again.
        </p>
      ) : !finished ? (
        <p className={`${card} px-6 py-10 text-center text-body`}>The scan is still running. Results appear here as soon as it finishes; you can leave this page.</p>
      ) : (
        <div className="flex flex-col gap-6">
          <dl className="grid overflow-hidden rounded-2xl border-2 border-ink bg-white shadow-hard sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Vulnerabilities" value={total} note={total === 0 ? "None found by the checks that ran" : "across all severities"} bad={critical > 0} />
            <Stat label="Critical and high" value={critical + (scan.high_count ?? 0)} note={`${critical} critical, ${scan.high_count ?? 0} high`} bad={critical > 0} />
            <Stat label="QA gaps" value={scan.gap_count ?? 0} note="Routes and flows without enough tests" />
            <Stat label="Test cases" value={scan.test_case_count ?? 0} note="written from this scan" />
          </dl>

          {total > 0 && (
            <section className={`${card} p-6`}>
              <h2 className="mb-4 text-lg font-bold">Vulnerabilities by severity</h2>
              <dl className="flex flex-col gap-2.5">
                {levels.map(([key, label, colour]) => {
                  const count = vulns.filter((v) => v.severity === key).length;
                  return (
                    <div key={key} className="flex items-center gap-3">
                      <dt className="w-28 flex-none text-[14.5px]">{label}</dt>
                      <div className="h-3 min-w-0 flex-1 overflow-hidden rounded-full bg-line">
                        <div className={`h-full ${colour}`} style={{ width: `${vulns.length ? (count / vulns.length) * 100 : 0}%` }} />
                      </div>
                      <dd className="w-8 flex-none text-right font-bold">{count}</dd>
                    </div>
                  );
                })}
              </dl>
            </section>
          )}

          <div className="grid gap-4 md:grid-cols-3">
            {[
              [`/scans/${id}/vulnerabilities`, "Vulnerabilities", "Every finding with its evidence and fix"],
              [`/scans/${id}/test-cases`, "Test cases", "Cases written for the pages found"],
              [`/scans/${id}/reports`, "Reports", "Create a PDF, JSON or CSV to share"],
            ].map(([to, title, note]) => (
              <Link key={to} to={to} className={`${card} flex flex-col gap-1 p-5 hover:border-ink`}>
                <span className="font-bold text-brand-600">{title}</span>
                <span className="text-[14.5px] text-body">{note}</span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </QuickScanShell>
  );
}
