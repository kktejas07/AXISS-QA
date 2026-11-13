import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus } from "lucide-react";
import { Layout } from "../components/Layout";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { SeverityBadge } from "../components/SeverityBadge";
import { getDashboardSummary } from "../api/dashboard";
import type { DashboardSummary, ScanStatus } from "../types";

const statusLabel: Record<ScanStatus, string> = {
  queued: "Queued",
  crawling: "Crawling",
  scanning: "Scanning",
  analyzing: "Analysing",
  completed: "Completed",
  failed: "Failed",
};

export function scanStatusClass(status: ScanStatus): string {
  if (status === "completed") return "bg-emerald-100 text-emerald-800";
  if (status === "failed") return "bg-red-100 text-red-800";
  if (status === "queued") return "bg-gray-100 text-gray-700";
  return "bg-brand-50 text-brand-700";
}

export function ScanStatusPill({ status, progress }: { status: ScanStatus; progress: number }) {
  const running = status === "crawling" || status === "scanning" || status === "analyzing";
  return (
    <span className={`inline-block whitespace-nowrap rounded-full px-2.5 py-1 text-[13px] font-bold ${scanStatusClass(status)}`}>
      {statusLabel[status] ?? status}
      {running ? `, ${progress}%` : ""}
    </span>
  );
}

function Stat({ label, value, note, tone }: { label: string; value: string | number; note: string; tone?: "bad" }) {
  return (
    <div className="flex flex-col gap-1 px-6 py-5 border-b border-line last:border-b-0 sm:border-b-0 sm:border-r sm:last:border-r-0">
      <dt className="text-sm font-semibold text-body">{label}</dt>
      <dd className={`text-[40px] leading-tight font-extrabold ${tone === "bad" ? "text-red-700" : ""}`}>{value}</dd>
      <span className="text-[13.5px] text-body">{note}</span>
    </div>
  );
}

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

export function Dashboard() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    getDashboardSummary()
      .then((r) => setData(r.data))
      .catch(() => setFailed(true));
  }, []);

  const header = (
    <div className="flex flex-wrap items-center justify-between gap-4 mb-7">
      <h1 className="text-4xl font-extrabold tracking-tight">Overview</h1>
      <Link
        to="/scans/new"
        className="flex items-center gap-2 h-[52px] px-5 rounded-[10px] bg-brand-600 hover:bg-brand-700 text-white font-bold"
      >
        <Plus className="w-[18px] h-[18px]" strokeWidth={2.4} aria-hidden="true" /> New scan
      </Link>
    </div>
  );

  if (failed) {
    return (
      <Layout>
        {header}
        <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-red-800">
          Your overview could not be loaded. Check that the API is running, then reload the page.
        </p>
      </Layout>
    );
  }
  if (!data) {
    return (
      <Layout>
        {header}
        <LoadingSpinner />
      </Layout>
    );
  }

  const v = data.open_vulnerabilities;
  const testTotal = Object.values(data.test_cases).reduce((a, b) => a + b, 0);
  const testTypes = Object.entries(data.test_cases).sort((a, b) => b[1] - a[1]);

  return (
    <Layout>
      {header}

      <dl className="mb-7 grid overflow-hidden rounded-2xl border-2 border-ink bg-white shadow-hard sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Critical findings open"
          value={v.critical}
          note={`${v.high} high, ${v.medium} medium`}
          tone={v.critical > 0 ? "bad" : undefined}
        />
        <Stat label="QA gaps" value={data.qa_gaps} note="Routes and flows without enough tests" />
        <Stat label="Tests generated" value={testTotal} note={`${data.test_cases.manual ?? 0} manual, ${testTotal - (data.test_cases.manual ?? 0)} automated`} />
        <Stat label="Scans" value={data.scans} note={`across ${plural(data.projects, "project")}`} />
      </dl>

      {data.scans === 0 ? (
        <section className="rounded-2xl border border-gray-300 bg-white px-6 py-12 text-center">
          <h2 className="text-xl font-bold">No scans yet</h2>
          <p className="mx-auto mt-2 max-w-md text-body">
            Paste a URL to audit an app for vulnerabilities and get test cases and scripts for it.
          </p>
          <Link to="/scans/new" className="mt-5 inline-flex h-12 items-center rounded-[10px] bg-ink px-5 font-bold text-white">
            Start your first scan
          </Link>
        </section>
      ) : (
        <div className="flex flex-wrap items-start gap-7">
          <div className="flex min-w-0 flex-[999_1_520px] flex-col gap-7">
            <section className="overflow-hidden rounded-2xl border border-gray-300 bg-white">
              <h2 className="px-5 py-4 text-lg font-bold">Recent scans</h2>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[560px] border-collapse text-left">
                  <thead>
                    <tr className="bg-soft text-[13.5px] text-body">
                      <th scope="col" className="px-5 py-2.5 font-semibold">App</th>
                      <th scope="col" className="px-3 py-2.5 font-semibold">Status</th>
                      <th scope="col" className="px-5 py-2.5 font-semibold">Open findings</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recent_scans.map((s) => (
                      <tr key={s.id} className="border-t border-line">
                        <td className="px-5 py-3.5">
                          <Link to={`/scans/${s.id}`} className="font-mono text-sm text-brand-600 hover:text-brand-700 break-all">
                            {s.url}
                          </Link>
                          <div className="text-[13.5px] text-body">{new Date(s.created_at).toLocaleString()}</div>
                        </td>
                        <td className="px-3 py-3.5">
                          <ScanStatusPill status={s.status} progress={s.progress} />
                        </td>
                        <td className="px-5 py-3.5 font-semibold whitespace-nowrap">
                          {s.total === 0 ? "None" : `${s.critical} critical, ${s.high} high, ${s.total} in all`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="overflow-hidden rounded-2xl border border-gray-300 bg-white">
              <h2 className="px-5 py-4 text-lg font-bold">Fix these first</h2>
              {data.top_findings.length === 0 ? (
                <p className="border-t border-line px-5 py-4 text-body">No open critical or high findings.</p>
              ) : (
                <ul>
                  {data.top_findings.map((f) => (
                    <li key={f.id} className="flex flex-wrap items-center gap-x-3.5 gap-y-2 border-t border-line px-5 py-3.5">
                      <SeverityBadge severity={f.severity} />
                      <Link to={`/scans/${f.scan_id}/vulnerabilities`} className="min-w-0 flex-[1_1_240px] font-semibold hover:text-brand-600">
                        {f.title}
                      </Link>
                      <span className="font-mono text-[13px] text-body break-all">{f.affected_url}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>

          <section className="flex min-w-0 flex-[1_1_300px] flex-col gap-3 rounded-2xl border border-gray-300 bg-white p-5">
            <h2 className="text-lg font-bold">Tests by type</h2>
            {testTypes.length === 0 ? (
              <p className="text-body">No tests generated yet. Open a completed scan and choose Generate tests.</p>
            ) : (
              <dl>
                {testTypes.map(([type, count]) => (
                  <div key={type} className="flex justify-between gap-2 border-b border-line py-2 last:border-b-0">
                    <dt className="text-body capitalize">{type.replace(/_/g, " ")}</dt>
                    <dd className="font-bold">{count}</dd>
                  </div>
                ))}
              </dl>
            )}
          </section>
        </div>
      )}
    </Layout>
  );
}
