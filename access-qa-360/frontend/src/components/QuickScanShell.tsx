import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Layout } from "./Layout";
import { getScan } from "../api/scans";
import type { Scan } from "../types";
import { backLink } from "./ui";

export type QuickTab = "overview" | "vulns" | "gaps" | "tests" | "reports";

const statusText: Record<Scan["status"], string> = {
  queued: "Queued", crawling: "Mapping pages", scanning: "Running checks", analyzing: "Analysing", completed: "Completed", failed: "Failed",
};

/** Heading and section links shared by the five pages of a quick security scan. */
export function QuickScanShell({ id, tab, children, onScan }: { id?: string; tab: QuickTab; children: React.ReactNode; onScan?: (scan: Scan) => void }) {
  const [scan, setScan] = useState<Scan | null>(null);
  const running = !!scan && scan.status !== "completed" && scan.status !== "failed";

  useEffect(() => {
    if (!id) return;
    let alive = true;
    const load = () =>
      getScan(id)
        .then((r) => {
          if (!alive) return;
          setScan(r.data);
          onScan?.(r.data);
        })
        .catch(() => {});
    load();
    // Keep asking only while the scan is still going.
    const timer = running ? setInterval(load, 3000) : undefined;
    return () => {
      alive = false;
      if (timer) clearInterval(timer);
    };
  }, [id, running]);

  const tabs: { key: QuickTab; label: string; to: string; count?: number }[] = [
    { key: "overview", label: "Overview", to: `/scans/${id}` },
    { key: "vulns", label: "Vulnerabilities", to: `/scans/${id}/vulnerabilities`, count: scan?.vulnerability_count },
    { key: "gaps", label: "QA gaps", to: `/scans/${id}/gaps`, count: scan?.gap_count },
    { key: "tests", label: "Test cases", to: `/scans/${id}/test-cases`, count: scan?.test_case_count },
    { key: "reports", label: "Reports", to: `/scans/${id}/reports` },
  ];

  return (
    <Layout>
      <div className="mb-6 flex flex-col gap-2">
        <Link to="/" className={backLink}>Overview</Link>
        <h1 className="break-all font-mono text-[28px] font-medium leading-tight">{scan?.url ?? "Quick security scan"}</h1>
        {scan && (
          <div className="flex flex-wrap items-center gap-x-3.5 gap-y-2 text-sm text-body">
            <span
              className={`whitespace-nowrap rounded-full px-2.5 py-1 text-[13px] font-bold ${
                scan.status === "completed" ? "bg-emerald-100 text-emerald-800" : scan.status === "failed" ? "bg-red-100 text-red-800" : "bg-brand-50 text-brand-700"
              }`}
            >
              {statusText[scan.status]}
              {running ? `, ${scan.progress}%` : ""}
            </span>
            <span>Quick security scan</span>
          </div>
        )}
      </div>

      {running && (
        <div role="progressbar" aria-valuenow={scan.progress} aria-valuemin={0} aria-valuemax={100} aria-label="Scan progress" className="mb-6 h-3 overflow-hidden rounded-full bg-line">
          <div className="h-full bg-brand-600 transition-[width] duration-500 motion-reduce:transition-none" style={{ width: `${scan.progress}%` }} />
        </div>
      )}

      <nav aria-label="Result sections" className="mb-6 flex flex-wrap gap-1.5 rounded-[14px] border border-gray-300 bg-white p-1.5">
        {tabs.map((t) => (
          <Link
            key={t.key}
            to={t.to}
            aria-current={t.key === tab ? "page" : undefined}
            className={`flex min-h-[44px] items-center gap-2 rounded-[10px] px-4 font-semibold ${t.key === tab ? "bg-ink text-white" : "text-ink hover:bg-soft"}`}
          >
            {t.label}
            {t.count !== undefined && <span className={`rounded-full px-2 text-[13px] font-bold text-ink ${t.key === tab ? "bg-white" : "bg-gray-100"}`}>{t.count}</span>}
          </Link>
        ))}
      </nav>

      {children}
    </Layout>
  );
}
