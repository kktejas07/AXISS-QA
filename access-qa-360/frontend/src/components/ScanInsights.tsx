import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Download } from "lucide-react";
import { getAudit } from "../api/audits";
import { getChanges, getStandards, standardsCsvPath, startSmokeRun } from "../api/insights";
import { useCan } from "../hooks/useMe";
import { apiError } from "../utils/errors";
import type { Changes, FlatFinding, ScanBrief, Standards } from "../api/insights";
import type { AuditJob } from "../api/audits";
import { downloadFromApi } from "../utils/download";
import { getFlows } from "../api/wise";
import type { FlowNode, Flows } from "../api/wise";
import { ApiBraces, CompareSheets, EmptyPanel, FlowMap, ShieldList, SpeedGauge } from "./Illustrations";
import { Dots, LoadingSpinner } from "./LoadingSpinner";
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

/** The crawled pages as a map: columns by how many clicks from the start page, arrows for links. */
export function FlowsTab({ job }: { job: AuditJob }) {
  const [data, setData] = useState<Flows | null>(null);
  const [error, setError] = useState("");
  const [picked, setPicked] = useState(0);

  useEffect(() => {
    getFlows(job.id).then((r) => setData(r.data)).catch(() => setError("The map could not be loaded. Try again."));
  }, [job.id]);

  if (error) return <p role="alert" className={errorBox}>{error}</p>;
  if (!data) return <LoadingSpinner label="Drawing the map" />;
  if (data.nodes.length === 0) {
    return (
      <EmptyPanel art={<FlowMap />} title="No pages to map">
        The map is drawn from the pages a website scan visits. This scan has none.
      </EmptyPanel>
    );
  }
  const columns: FlowNode[][] = [];
  data.nodes.forEach((n) => (columns[n.depth] ??= []).push(n));
  const W = 190, H = 58, GX = 70, GY = 18;
  const place = new Map<number, { x: number; y: number }>();
  columns.forEach((col, c) => col?.forEach((n, r) => place.set(n.id, { x: 12 + c * (W + GX), y: 12 + r * (H + GY) })));
  const width = 24 + columns.length * W + (columns.length - 1) * GX;
  const height = 24 + Math.max(...columns.map((c) => c?.length ?? 0)) * (H + GY) - GY;
  const node = data.nodes[picked] ?? data.nodes[0];
  const touches = (e: { from: number; to: number }) => e.from === node.id || e.to === node.id;
  return (
    <div className="flex flex-col gap-5">
      <p className="max-w-[72ch] text-body">
        How the pages link to each other, starting from the address you gave. Pick a page to see its forms and the requests it makes.
        {data.pages_crawled > data.shown && ` The first ${data.shown} of ${data.pages_crawled} pages are shown.`}
      </p>
      <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
        <div className={`${card} relative overflow-x-auto p-2`}>
          <svg viewBox={`0 0 ${width} ${height}`} style={{ width, minWidth: "100%", height }} role="group" aria-label="Map of the pages and the links between them">
            <defs>
              <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M0 0l10 5-10 5z" fill="#818cf8" />
              </marker>
              <marker id="arrow-on" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M0 0l10 5-10 5z" fill="#101014" />
              </marker>
            </defs>
            {data.edges.map((e, i) => {
              const a = place.get(e.from)!, b = place.get(e.to)!;
              const forward = b.x > a.x;
              const x1 = forward ? a.x + W : a.x, x2 = forward ? b.x : b.x + (b.x === a.x ? 0 : W);
              const y1 = a.y + H / 2, y2 = b.y + H / 2, bend = forward ? GX / 2 : -GX / 2;
              const on = touches(e);
              return (
                <path key={i} d={`M${x1} ${y1}C${x1 + bend} ${y1} ${x2 - bend} ${y2} ${x2} ${y2}`} fill="none" stroke={on ? "#101014" : "#c7d2fe"} strokeWidth={on ? 2.2 : 1.4}
                  markerEnd={`url(#${on ? "arrow-on" : "arrow"})`} className={on ? "wf-flow" : undefined} />
              );
            })}
            {data.nodes.map((n) => {
              const { x, y } = place.get(n.id)!;
              const on = n.id === node.id;
              return (
                <g key={n.id} role="button" tabIndex={0} aria-pressed={on} aria-label={`Page ${n.path}`} className="cursor-pointer outline-none [&:focus-visible>rect]:stroke-[3]"
                  onClick={() => setPicked(n.id)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setPicked(n.id); } }}>
                  {on && <rect x={x + 5} y={y + 5} width={W} height={H} rx="10" fill="#3730a3" />}
                  <rect x={x} y={y} width={W} height={H} rx="10" fill={on ? "#eef2ff" : "#fff"} stroke={on ? "#101014" : "#9ca3af"} strokeWidth={on ? 2.2 : 1.2} />
                  <text x={x + 12} y={y + 24} fontSize="13" fontWeight="700" fontFamily="Roboto Mono, monospace" fill="#101014">{n.path.length > 20 ? `${n.path.slice(0, 19)}…` : n.path}</text>
                  <text x={x + 12} y={y + 43} fontSize="11.5" fill="#4b4f5c">{(n.title || "Untitled").slice(0, 26)}</text>
                  {n.forms > 0 && <circle cx={x + W - 16} cy={y + 16} r="6" fill="#4338ca" />}
                </g>
              );
            })}
          </svg>
        </div>
        <aside aria-label="The page you picked" className={`${card} wf-fade-up flex flex-col gap-3 self-start p-5`} key={node.id}>
          <h2 className="break-all font-mono text-lg font-bold">{node.path}</h2>
          <p className="text-body">{node.title || "This page has no title."}</p>
          <dl className="grid grid-cols-2 gap-3 text-[15px]">
            {[
              ["Links out", data.edges.filter((e) => e.from === node.id).length],
              ["Links in", data.edges.filter((e) => e.to === node.id).length],
              ["Accessibility problems", node.a11y],
              ["Largest paint", seconds(node.lcp_ms)],
            ].map(([k, v]) => (
              <div key={k}>
                <dt className="text-[13px] font-semibold text-body">{k}</dt>
                <dd className="font-bold">{v}</dd>
              </div>
            ))}
          </dl>
          <div>
            <h3 className="text-[13px] font-semibold text-body">Form fields</h3>
            {node.form_fields.length ? (
              <ul className="mt-1 flex flex-wrap gap-1.5">{node.form_fields.map((f, i) => <li key={i} className="rounded-full bg-brand-50 px-2.5 py-0.5 font-mono text-[12.5px] text-brand-700">{f}</li>)}</ul>
            ) : (
              <p>{node.forms ? `${node.forms} form${node.forms === 1 ? "" : "s"}, fields not recorded` : "No forms on this page"}</p>
            )}
          </div>
          <div>
            <h3 className="text-[13px] font-semibold text-body">Requests the page makes</h3>
            {node.api_calls.length ? (
              <ul className="mt-1 flex flex-col gap-1">{node.api_calls.map((c, i) => <li key={i} className="break-all font-mono text-[12.5px]">{c}</li>)}</ul>
            ) : (
              <p>None seen</p>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}

const verdictLook: Record<string, [string, string]> = {
  pass: ["Passed", "bg-emerald-100 text-emerald-900"],
  fail: ["Failed", "bg-red-100 text-red-900"],
  review: ["Check by hand", "bg-amber-100 text-amber-900"],
  error: ["No answer", "bg-gray-200 text-ink"],
};

/** Chatbot scans: every test message, what the bot replied, and the verdict. */
export function ConversationsTab({ job }: { job: AuditJob }) {
  const result = job.tier1_result?.chatbot;
  const [show, setShow] = useState<"all" | "problems">("problems");
  if (!result) {
    return (
      <EmptyPanel art={<ShieldList />} title="The chatbot was not tested">
        {job.tier1_result?.error ?? "No test messages have been sent yet."}
      </EmptyPanel>
    );
  }
  const problems = result.probes.filter((p) => p.verdict !== "pass");
  const shown = show === "all" ? result.probes : problems;
  return (
    <div className="flex flex-col gap-5">
      <p className="max-w-[72ch] text-body">{result.note}</p>
      <dl className="grid gap-4 sm:grid-cols-4">
        {[["Passed", result.passed, ""], ["Failed", result.failed, result.failed ? "text-red-800" : ""], ["Check by hand", result.review, ""], ["No answer", result.errors, ""]].map(([k, v, tone]) => (
          <div key={k} className={`${card} p-5`}>
            <dt className="text-[13.5px] font-semibold text-body">{k}</dt>
            <dd className={`text-2xl font-extrabold ${tone}`}>{v}</dd>
          </div>
        ))}
      </dl>
      <div role="group" aria-label="Which conversations to show" className="flex gap-1 self-start rounded-[11px] border border-gray-300 bg-white p-1">
        {([["problems", `Needs attention (${problems.length})`], ["all", `All (${result.probes.length})`]] as const).map(([id, text]) => (
          <button key={id} type="button" aria-pressed={show === id} onClick={() => setShow(id)} className={`min-h-[40px] rounded-[8px] px-3.5 text-sm font-semibold ${show === id ? "bg-ink text-white" : "text-ink"}`}>
            {text}
          </button>
        ))}
      </div>
      {shown.length === 0 ? (
        <p className={`${card} px-6 py-10 text-center text-body`}>Every test message got a safe reply.</p>
      ) : (
        <ul className="flex flex-col gap-4">
          {shown.map((p, i) => (
            <li key={p.id} className={`${card} wf-fade-up flex flex-col gap-3 p-5`} style={{ animationDelay: `${Math.min(i, 8) * 40}ms` }}>
              <div className="flex flex-wrap items-center gap-2.5">
                <span className={`rounded-full px-2.5 py-0.5 text-[13px] font-bold ${verdictLook[p.verdict][1]}`}>{verdictLook[p.verdict][0]}</span>
                <span className="text-[13.5px] font-semibold text-body">{p.category}</span>
                <h2 className="w-full text-lg font-bold">{p.name}</h2>
              </div>
              <p className="max-w-[90%] self-end whitespace-pre-wrap break-words rounded-2xl rounded-br-md bg-ink px-3.5 py-2.5 text-[15px] text-white">{p.prompt}</p>
              {p.reply && <p className="max-w-[90%] self-start whitespace-pre-wrap break-words rounded-2xl rounded-bl-md bg-soft px-3.5 py-2.5 text-[15px]">{p.reply}</p>}
              <p className="text-[15px]"><span className="font-semibold">Verdict:</span> {p.why}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const smokeLook: Record<string, [string, string]> = {
  pass: ["Loads", "bg-emerald-100 text-emerald-900"],
  warn: ["Loads, with problems", "bg-amber-100 text-amber-900"],
  fail: ["Broken", "bg-red-100 text-red-900"],
};

/**
 * Website scans: open every mapped page again in a real browser, now, and show which still load.
 * The steps are Wiseflow's own; the AI-written scripts below it are for the person's own pipeline.
 */
export function SmokeTest({ job }: { job: AuditJob }) {
  const canRun = useCan("scan.run");
  const [run, setRun] = useState(job.tier1_result?.smoke_run);
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(false);
  const running = run?.state === "running";

  // While a run is in progress, ask the server every few seconds whether it has finished.
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => {
      getAudit(job.id).then((r) => setRun(r.data.tier1_result?.smoke_run)).catch(() => {});
    }, 3000);
    return () => clearInterval(timer);
  }, [running, job.id]);

  const start = async () => {
    setError("");
    setStarting(true);
    try {
      const { data } = await startSmokeRun(job.id);
      setRun({ state: "running", total: data.total, pages: [] });
    } catch (e) {
      setError(apiError(e, "The smoke test could not be started. Try again."));
    } finally {
      setStarting(false);
    }
  };

  return (
    <section className={`${card} overflow-hidden`}>
      <div className="flex flex-wrap items-center justify-between gap-4 p-5">
        <div className="min-w-0 flex-1">
          <h2 className="text-lg font-bold">Smoke test</h2>
          <p className="max-w-[64ch] text-body">
            Wiseflow opens each page this scan mapped in a real browser and checks that it still loads, the server answers without an error, and the page's script does not crash. Public pages only.
          </p>
        </div>
        {canRun && (
          <button type="button" onClick={start} disabled={running || starting} className="flex h-12 items-center gap-2 rounded-[10px] bg-brand-600 px-5 font-bold text-white hover:bg-brand-700 disabled:opacity-60">
            {running ? "Running" : run ? "Run again" : "Run a smoke test"}
          </button>
        )}
      </div>
      {error && <p role="alert" className={`${errorBox} mx-5 mb-5`}>{error}</p>}
      {running && (
        <div role="status" className="flex items-center gap-3 border-t border-line px-5 py-4">
          <Dots />
          <span>Opening {run?.total ?? "the"} pages. This takes up to a minute.</span>
        </div>
      )}
      {run?.state === "failed" && <p role="alert" className={`${errorBox} mx-5 mb-5`}>{run.error}</p>}
      {run?.state === "done" && (
        <div className="border-t border-line">
          <p role="status" className="px-5 py-3 font-semibold">
            {run.failed ? `${run.failed} of ${run.pages.length} pages are broken.` : run.warned ? `Every page loads; ${run.warned} have problems worth a look.` : `All ${run.pages.length} pages load cleanly.`}
            <span className="font-normal text-body"> Run on {new Date(run.finished_at!).toLocaleString()}.</span>
          </p>
          <ul className="divide-y divide-line border-t border-line">
            {run.pages.map((p) => (
              <li key={p.url} className="flex flex-col gap-1 px-5 py-3">
                <span className="flex flex-wrap items-center gap-2.5">
                  <span className={`rounded-full px-2.5 py-0.5 text-[13px] font-bold ${smokeLook[p.verdict][1]}`}>{smokeLook[p.verdict][0]}</span>
                  <span className="break-all font-mono text-sm font-semibold">{p.path}</span>
                  <span className="text-[13.5px] text-body">{p.status ? `status ${p.status}` : "no answer"}{p.ms !== null ? `, ${(p.ms / 1000).toFixed(1)} s` : ""}</span>
                </span>
                {p.problems.map((text, i) => <span key={i} className="break-words text-[14.5px]">{text}</span>)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
