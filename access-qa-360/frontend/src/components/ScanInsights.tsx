import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Download } from "lucide-react";
import { getChanges, getStandards, standardsCsvPath } from "../api/insights";
import type { Changes, FlatFinding, ScanBrief, Standards } from "../api/insights";
import type { AuditJob } from "../api/audits";
import { downloadFromApi } from "../utils/download";
import { ApiBraces, CompareSheets, EmptyPanel, ShieldList, SpeedGauge } from "./Illustrations";
import { LoadingSpinner } from "./LoadingSpinner";
import { SeverityTag } from "./ScanResults";
import { card, errorBox } from "./ui";

const day = (iso: string) => new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });

function FindingList({ items, empty }: { items: FlatFinding[]; empty: string }) {
  if (items.length === 0) return <p className="px-5 py-4 text-body">{empty}</p>;
  return (
    <ul className="divide-y divide-line">
      {items.map((f, i) => (
        <li key={`${f.source}-${f.index}-${i}`} className="flex flex-col gap-1 px-5 py-3">
          <span className="flex flex-wrap items-center gap-2.5">
            <SeverityTag severity={f.severity} />
            <span className="font-semibold">{f.title}</span>
          </span>
          {f.location && <span className="break-all font-mono text-[13px] text-body">{f.location}</span>}
        </li>
      ))}
    </ul>
  );
}

/** Risk score of each scan of this target, oldest to newest. Lower is better. */
export function TrendChart({ history, currentId }: { history: ScanBrief[]; currentId: string }) {
  const points = history.filter((h) => h.risk_score !== null);
  if (points.length < 2) return null;
  const w = 560, h = 150, left = 34, right = 14, top = 14, bottom = 28;
  const x = (i: number) => left + (i * (w - left - right)) / (points.length - 1);
  const y = (score: number) => top + ((100 - score) * (h - top - bottom)) / 100;
  const path = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(p.risk_score!).toFixed(1)}`).join(" ");
  return (
    <figure className={`${card} p-5`}>
      <figcaption className="mb-2 font-bold">Risk score over time <span className="font-normal text-body">(0 to 100, lower is better)</span></figcaption>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" role="img" aria-label={`Risk score for the last ${points.length} scans: ${points.map((p) => p.risk_score).join(", ")}`}>
        {[0, 50, 100].map((v) => (
          <g key={v}>
            <line x1={left} x2={w - right} y1={y(v)} y2={y(v)} stroke="#e6e7ee" />
            <text x={left - 8} y={y(v) + 4} textAnchor="end" fontSize="11" fill="#4b4f5c">{v}</text>
          </g>
        ))}
        <path d={path} fill="none" stroke="#4338ca" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />
        {points.map((p, i) => (
          <g key={p.id}>
            <circle cx={x(i)} cy={y(p.risk_score!)} r={p.id === currentId ? 6 : 4} fill={p.id === currentId ? "#101014" : "#fff"} stroke="#4338ca" strokeWidth="2.5" />
            <text x={x(i)} y={h - 8} textAnchor={i === 0 ? "start" : i === points.length - 1 ? "end" : "middle"} fontSize="11" fill="#4b4f5c">{day(p.created_at)}</text>
          </g>
        ))}
      </svg>
    </figure>
  );
}

export function ChangesTab({ job }: { job: AuditJob }) {
  const [data, setData] = useState<Changes | null>(null);
  const [against, setAgainst] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    setError("");
    getChanges(job.id, against || undefined)
      .then((r) => setData(r.data))
      .catch(() => setError("The comparison could not be loaded. Try again."));
  }, [job.id, against]);

  if (error) return <p role="alert" className={errorBox}>{error}</p>;
  if (!data) return <LoadingSpinner />;
  if (!data.baseline) {
    return (
      <EmptyPanel art={<CompareSheets />} title="Nothing to compare with yet">
        This is the first finished scan of {job.label}. Scan it again later and this tab will show which findings are new and which were fixed.
      </EmptyPanel>
    );
  }
  const earlier = data.history.filter((h) => h.id !== job.id);
  const change = (data.scan.risk_score ?? 0) - (data.baseline.risk_score ?? 0);
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <p className="text-body">
          Compared with the scan from <Link to={`/audits/${data.baseline.id}`} className="font-semibold text-brand-600">{new Date(data.baseline.created_at).toLocaleString()}</Link>.
        </p>
        {earlier.length > 1 && (
          <label className="flex flex-col gap-1.5 text-sm font-semibold">
            Compare with
            <select value={against || data.baseline.id} onChange={(e) => setAgainst(e.target.value)} className="h-11 rounded-[10px] border border-gray-400 bg-white px-3">
              {earlier.map((h) => <option key={h.id} value={h.id}>{new Date(h.created_at).toLocaleString()}</option>)}
            </select>
          </label>
        )}
      </div>
      <dl className="grid gap-4 sm:grid-cols-4">
        {[
          ["New findings", data.new.length],
          ["Fixed", data.fixed.length],
          ["Unchanged", data.unchanged],
          ["Risk score", `${data.scan.risk_score ?? "–"} (${change === 0 ? "no change" : change > 0 ? `up ${change}` : `down ${-change}`})`],
        ].map(([k, v]) => (
          <div key={k} className={`${card} p-5`}>
            <dt className="text-[13.5px] font-semibold text-body">{k}</dt>
            <dd className="text-2xl font-extrabold">{v}</dd>
          </div>
        ))}
      </dl>
      <TrendChart history={data.history} currentId={job.id} />
      <section className={`${card} overflow-hidden`}>
        <h2 className="border-b border-line px-5 py-3.5 font-bold">New since that scan</h2>
        <FindingList items={data.new} empty="Nothing new was found." />
      </section>
      <section className={`${card} overflow-hidden`}>
        <h2 className="border-b border-line px-5 py-3.5 font-bold">Fixed since that scan</h2>
        <FindingList items={data.fixed} empty="Nothing from the earlier scan has gone away." />
      </section>
    </div>
  );
}

export function StandardsTab({ job }: { job: AuditJob }) {
  const [data, setData] = useState<Standards | null>(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    getStandards(job.id).then((r) => setData(r.data)).catch(() => setError("The standards view could not be loaded. Try again."));
  }, [job.id]);

  if (error) return <p role="alert" className={errorBox}>{error}</p>;
  if (!data) return <LoadingSpinner />;
  const total = data.categories.reduce((n, c) => n + c.count, 0) + data.other.length;
  if (total === 0) {
    return (
      <EmptyPanel art={<ShieldList />} title="No security findings to sort">
        This scan has no security findings, so there is nothing to place in the OWASP Top 10. That is not proof the app meets the standard: it only covers what this scan checked.
      </EmptyPanel>
    );
  }
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <p className="max-w-[70ch] text-body">
          Where this scan's security findings fall in the {data.standard}. {data.covered} of 10 categories have findings. An empty category means this scan found nothing there, not that the app is certified.
        </p>
        <button type="button" onClick={() => downloadFromApi(standardsCsvPath(job.id), "wiseflow-standards.csv")} className="flex h-11 items-center gap-2 rounded-[10px] border-[1.5px] border-ink bg-white px-4 text-sm font-semibold">
          <Download className="h-4 w-4" aria-hidden="true" />
          Download as CSV
        </button>
      </div>
      <ul className={`${card} divide-y divide-line overflow-hidden`}>
        {data.categories.map((c) => (
          <li key={c.code}>
            <button
              type="button"
              disabled={c.count === 0}
              aria-expanded={open === c.code}
              onClick={() => setOpen(open === c.code ? null : c.code)}
              className="flex min-h-[56px] w-full items-center gap-4 px-5 py-3 text-left enabled:hover:bg-soft"
            >
              <span className="w-10 font-mono text-sm font-bold text-brand-700">{c.code}</span>
              <span className={`flex-1 font-semibold ${c.count === 0 ? "text-body" : ""}`}>{c.name}</span>
              {c.worst && <SeverityTag severity={c.worst} />}
              <span className={`min-w-[2.5rem] rounded-full px-2.5 py-0.5 text-center text-sm font-bold ${c.count ? "bg-ink text-white" : "bg-gray-100 text-body"}`}>{c.count}</span>
            </button>
            {open === c.code && <div className="border-t border-line bg-soft"><FindingList items={c.findings} empty="" /></div>}
          </li>
        ))}
      </ul>
      {data.other.length > 0 && (
        <section className={`${card} overflow-hidden`}>
          <h2 className="border-b border-line px-5 py-3.5 font-bold">Findings outside the Top 10</h2>
          <FindingList items={data.other} empty="" />
        </section>
      )}
    </div>
  );
}

const seconds = (ms: number | null | undefined) => (ms === null || ms === undefined ? "Not measured" : `${(ms / 1000).toFixed(1)} s`);
const megabytes = (bytes: number | null | undefined) => (bytes === null || bytes === undefined ? "Not measured" : `${(bytes / 1_000_000).toFixed(1)} MB`);
// [key, label, how to show it, "needs work" above this]. The limits match the server's.
const perfColumns: [string, string, (v: number | null | undefined) => string, number][] = [
  ["lcp_ms", "Largest paint", seconds, 2500],
  ["fcp_ms", "First paint", seconds, 1800],
  ["ttfb_ms", "First byte", seconds, 800],
  ["bytes", "Page weight", megabytes, 1_500_000],
];

/** How fast each page loaded during the scan. */
export function PerformanceTab({ job }: { job: AuditJob }) {
  const perf = job.tier1_result?.performance;
  if (!perf || perf.pages_measured === 0) {
    return (
      <EmptyPanel art={<SpeedGauge />} title="No pages were timed">
        Load times are measured while the site is crawled. This scan has none, either because it ran before this was added or because no page could be loaded.
      </EmptyPanel>
    );
  }
  return (
    <div className="flex flex-col gap-5">
      <p className="max-w-[72ch] text-body">{perf.note}</p>
      <dl className="grid gap-4 sm:grid-cols-4">
        {perfColumns.map(([key, name, show, limit]) => {
          const value = perf.averages[key];
          const slow = value !== null && value !== undefined && value > limit;
          return (
            <div key={key} className={`${card} p-5`}>
              <dt className="text-[13.5px] font-semibold text-body">{name}, average</dt>
              <dd className={`text-2xl font-extrabold ${slow ? "text-red-800" : ""}`}>{show(value)}</dd>
              <dd className="text-[13px] text-body">{slow ? `Over the recommended ${show(limit)}` : `Within the recommended ${show(limit)}`}</dd>
            </div>
          );
        })}
      </dl>
      {perf.findings.length > 0 && (
        <section className={`${card} overflow-hidden`}>
          <h2 className="border-b border-line px-5 py-3.5 font-bold">What to fix</h2>
          <ul className="divide-y divide-line">
            {perf.findings.map((f, i) => (
              <li key={i} className="flex flex-col gap-1 px-5 py-3">
                <span className="flex flex-wrap items-center gap-2.5">
                  <SeverityTag severity={f.severity} />
                  <span className="font-semibold">{f.title}</span>
                </span>
                <span className="break-all font-mono text-[13px] text-body">{f.affected_url}</span>
                <span>{f.description} {f.remediation}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      <section className={`${card} overflow-hidden`}>
        <h2 className="border-b border-line px-5 py-3.5 font-bold">Every page that was timed</h2>
        <div className="relative overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-[15px]">
            <thead className="text-[13.5px] text-body">
              <tr>
                <th scope="col" className="px-5 py-2.5 font-semibold">Page</th>
                {perfColumns.map(([key, name]) => <th key={key} scope="col" className="px-4 py-2.5 font-semibold">{name}</th>)}
                <th scope="col" className="px-4 py-2.5 font-semibold">Requests</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {perf.pages.map((p) => (
                <tr key={p.url}>
                  <td className="max-w-[320px] break-all px-5 py-2.5 font-mono text-[13px]">{p.url.replace(/^https?:\/\/[^/]+/, "") || "/"}</td>
                  {perfColumns.map(([key, , show, limit]) => {
                    const value = (p as unknown as Record<string, number | null>)[key];
                    return <td key={key} className={`px-4 py-2.5 ${value !== null && value > limit ? "font-bold text-red-800" : ""}`}>{show(value)}</td>;
                  })}
                  <td className="px-4 py-2.5">{p.requests}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

/** API description scans: every endpoint in the file and whether it needs sign-in. */
export function EndpointsTab({ job }: { job: AuditJob }) {
  const api = job.tier1_result?.api;
  if (!api) {
    return (
      <EmptyPanel art={<ApiBraces />} title="No endpoints to show">
        {job.tier1_result?.error ?? "The API description has not been read yet."}
      </EmptyPanel>
    );
  }
  return (
    <div className="flex flex-col gap-5">
      <p className="text-body">
        {api.title}{api.version && `, version ${api.version}`} ({api.format}). {api.secured} of {api.operations} endpoints need sign-in. {job.tier3_result?.live}
      </p>
      <section className={`${card} overflow-hidden`}>
        <div className="relative overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-[15px]">
            <thead className="text-[13.5px] text-body">
              <tr>
                <th scope="col" className="px-5 py-2.5 font-semibold">Method</th>
                <th scope="col" className="px-4 py-2.5 font-semibold">Path</th>
                <th scope="col" className="px-4 py-2.5 font-semibold">What it does</th>
                <th scope="col" className="px-4 py-2.5 font-semibold">Sign-in</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {api.endpoints.map((e) => (
                <tr key={`${e.method} ${e.path}`}>
                  <td className="px-5 py-2.5 font-mono text-[13px] font-bold">{e.method}</td>
                  <td className="break-all px-4 py-2.5 font-mono text-[13px]">{e.path}</td>
                  <td className="px-4 py-2.5">{e.summary || "Not described"}</td>
                  <td className={`px-4 py-2.5 font-semibold ${e.secured ? "" : "text-orange-800"}`}>{e.secured ? "Required" : "Not required"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
