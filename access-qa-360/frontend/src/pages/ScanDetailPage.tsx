import { useEffect, useState } from "react";
import { Link, Navigate, useParams, useSearchParams } from "react-router-dom";
import { Check, Minus, X } from "lucide-react";
import { Layout } from "../components/Layout";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ChangesTab, EndpointsTab, FlowsTab, PerformanceTab, StandardsTab } from "../components/ScanInsights";
import { ScanSteps } from "../components/ScanSteps";
import { StatusPill } from "../components/StatusPill";
import {
  AccessibilityTab,
  AutomationTab,
  DownloadButton,
  DownloadsTab,
  QaGapsTab,
  SecurityTab,
  SeverityTag,
  TestCasesTab,
  allFindings,
} from "../components/ScanResults";
import { getAudit, isCode, sourceName, stopAudit } from "../api/audits";
import { useCan } from "../hooks/useMe";
import { apiError } from "../utils/errors";
import type { AuditJob, StepStatus } from "../api/audits";


type Step = { name: string; doing: string; status: StepStatus; problem?: string };

function stepsOf(job: AuditJob): Step[] {
  const why = (r?: { error?: string; skipped?: string } | null) => r?.error ?? r?.skipped;
  if (isCode(job)) {
    // Source code scans have no mobile step, and the first step reads files instead of pages.
    return [
      { name: "Read the code", doing: job.source_type === "repo" ? "Cloning the repository, listing files and routes, finding missing tests" : "Unpacking the upload, listing files and routes, finding missing tests", status: job.tier1_status, problem: why(job.tier1_result) },
      { name: "Run security checks", doing: "Looking for leaked secrets, risky code and vulnerable dependencies", status: job.tier3_status, problem: why(job.tier3_result) },
      { name: "Write manual test cases", doing: "Writing cases for the routes found in the code", status: job.tier4_status, problem: why(job.tier4_result) },
      { name: "Write the report", doing: "Summarising the results and building the PDF", status: job.tier5_status, problem: why(job.tier5_result) },
    ];
  }
  return [
    { name: "Map the web app", doing: "Opening pages, checking accessibility and writing web tests", status: job.tier1_status, problem: why(job.tier1_result) },
    { name: "Analyse the mobile build", doing: "Reading permissions and settings, writing mobile tests", status: job.tier2_status, problem: why(job.tier2_result) },
    { name: "Run security checks", doing: "Testing headers, sign-in, access control and exposed secrets", status: job.tier3_status, problem: why(job.tier3_result) },
    { name: "Collect manual test cases", doing: "Putting web and mobile cases into one list", status: job.tier4_status, problem: why(job.tier4_result) },
    { name: "Write the report", doing: "Summarising the results and building the PDF", status: job.tier5_status, problem: why(job.tier5_result) },
  ];
}

function StepIcon({ status, n }: { status: StepStatus; n: number }) {
  const base = "flex h-7 w-7 flex-none items-center justify-center rounded-full text-[13px] font-bold";
  if (status === "completed") return <span className={`${base} bg-ink text-white`}><Check className="h-3.5 w-3.5" strokeWidth={3} aria-hidden="true" /></span>;
  if (status === "failed") return <span className={`${base} bg-red-700 text-white`}><X className="h-3.5 w-3.5" strokeWidth={3} aria-hidden="true" /></span>;
  if (status === "skipped") return <span className={`${base} border-[1.5px] border-gray-400 text-body`}><Minus className="h-3.5 w-3.5" aria-hidden="true" /></span>;
  if (status === "running") return <span className={`${base} animate-pulse bg-brand-600 text-white motion-reduce:animate-none`}>{n}</span>;
  return <span className={`${base} border-[1.5px] border-gray-400 text-body`}>{n}</span>;
}

const stepWord: Record<StepStatus, string> = { pending: "Waiting", running: "Running", completed: "Done", failed: "Failed", skipped: "Skipped" };

function StepList({ job }: { job: AuditJob }) {
  return (
    <ol aria-label="Scan steps" className="overflow-hidden rounded-2xl border border-gray-300 bg-white">
      {stepsOf(job).map((s, i) => (
        <li key={s.name} className={`flex items-start gap-3.5 px-[22px] py-4 ${i ? "border-t border-line" : ""} ${s.status === "running" ? "bg-brand-50" : ""}`}>
          <StepIcon status={s.status} n={i + 1} />
          <div className="min-w-0 flex-1">
            <div className="font-bold">{s.name}</div>
            <div className={`break-words text-[14.5px] ${s.status === "failed" ? "text-red-800" : "text-body"}`}>
              {s.status === "failed" || s.status === "skipped" ? s.problem ?? s.doing : s.doing}
            </div>
          </div>
          <span className={`whitespace-nowrap text-[13.5px] ${s.status === "running" ? "font-bold text-brand-700" : s.status === "failed" ? "font-bold text-red-800" : "text-body"}`}>
            {stepWord[s.status]}
          </span>
        </li>
      ))}
    </ol>
  );
}

function Stat({ label, value, note, bad }: { label: string; value: string | number; note: string; bad?: boolean }) {
  return (
    <div className="flex flex-col gap-1 border-b border-line px-6 py-5 last:border-b-0 sm:border-b-0 sm:border-r sm:last:border-r-0">
      <dt className="text-sm font-semibold text-body">{label}</dt>
      <dd className={`text-[40px] font-extrabold leading-tight ${bad ? "text-red-700" : ""}`}>{value}</dd>
      <span className="text-[13.5px] text-body">{note}</span>
    </div>
  );
}

type TabId = "summary" | "security" | "accessibility" | "gaps" | "cases" | "code" | "changes" | "standards" | "performance" | "endpoints" | "flows" | "downloads";

/** One scan: progress while it runs, then tabbed results. */
export function ScanDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [params, setParams] = useSearchParams();
  const [job, setJob] = useState<AuditJob | null>(null);
  const [missing, setMissing] = useState(false);
  const canStop = useCan("scan.run");
  const [stopping, setStopping] = useState(false);
  const [stopError, setStopError] = useState("");

  const stop = async () => {
    if (!id) return;
    setStopError("");
    setStopping(true);
    try {
      setJob((await stopAudit(id)).data);
    } catch (e) {
      setStopError(apiError(e, "The scan could not be stopped. Try again."));
    } finally {
      setStopping(false);
    }
  };

  const loaded = job !== null;
  const active = job?.status === "queued" || job?.status === "running";

  useEffect(() => {
    if (!id) return;
    let alive = true;
    const load = () =>
      getAudit(id)
        .then((r) => alive && setJob(r.data))
        .catch(() => alive && setMissing(true));
    load();
    // Keep asking only while the scan is still going.
    const timer = loaded && active ? setInterval(load, 2500) : undefined;
    return () => {
      alive = false;
      if (timer) clearInterval(timer);
    };
  }, [id, loaded, active]);

  if (missing) {
    return (
      <Layout>
        <h1 className="mb-4 text-4xl font-extrabold tracking-tight">Scan not found</h1>
        <Link to="/audits" className="font-semibold text-brand-600">Back to your scans</Link>
      </Layout>
    );
  }
  if (!job) {
    return (
      <Layout>
        <LoadingSpinner />
      </Layout>
    );
  }
  if (!job.started_at) return <Navigate to={`/audits/${job.id}/setup`} replace />;

  const code = isCode(job);
  const title = <h1 className="break-all font-mono text-[28px] font-medium leading-tight">{job.target_url ?? job.label}</h1>;

  // ---- still running -------------------------------------------------------
  if (active) {
    return (
      <Layout>
        <div className="mb-7 flex flex-col gap-5">
          <h1 className="text-4xl font-extrabold tracking-tight">{code ? "Scanning your code" : "Scanning your app"}</h1>
          <ScanSteps current={3} />
        </div>
        <section className="mb-7 flex flex-col gap-4 rounded-2xl border-2 border-ink bg-white p-6 shadow-hard">
          <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
            <span className="break-all font-mono text-lg font-medium">{job.target_url ?? job.label}</span>
            <span className="text-body">Started {new Date(job.started_at).toLocaleTimeString()}</span>
          </div>
          <div role="progressbar" aria-valuenow={job.progress} aria-valuemin={0} aria-valuemax={100} aria-label="Scan progress" className="h-3.5 overflow-hidden rounded-full bg-line">
            <div className="h-full bg-brand-600 transition-[width] duration-500 motion-reduce:transition-none" style={{ width: `${job.progress}%` }} />
          </div>
          <span className="font-semibold">{job.progress}% done. You can leave this page; the scan keeps running and appears under Scans.</span>
          {canStop && (
            <div className="flex flex-wrap items-center gap-3 border-t border-line pt-4">
              <button type="button" onClick={stop} disabled={stopping} className="h-11 rounded-[10px] border-[1.5px] border-red-700 bg-white px-4 text-sm font-semibold text-red-800 disabled:opacity-60">
                {stopping ? "Stopping" : "Stop scan"}
              </button>
              <span className="text-[13.5px] text-body">Steps that already finished keep their results.</span>
              {stopError && <span role="alert" className="text-[13.5px] text-red-800">{stopError}</span>}
            </div>
          )}
        </section>
        <StepList job={job} />
      </Layout>
    );
  }

  // ---- finished ------------------------------------------------------------
  const api = job.source_type === "api";
  const findings = allFindings(job);
  const a11y = job.tier1_result?.a11y_summary?.violations.length ?? 0;
  const cases = job.tier4_result?.test_cases?.length ?? 0;
  const gaps = job.tier1_result?.qa_gaps;
  const gapCount = (gaps?.untested_route_count ?? 0) + (gaps?.untested_file_count ?? 0);
  const languages = Object.keys(job.tier1_result?.languages ?? {});
  // A code scan has no pages to check for accessibility and writes no automation; it reports missing tests instead.
  const tabs: { id: TabId; label: string; count?: number }[] = [
    { id: "summary", label: "Summary" },
    { id: "security", label: "Security", count: findings.length },
    ...(code
      ? [{ id: "gaps" as const, label: "QA gaps", count: gapCount }]
      : api
        ? [{ id: "endpoints" as const, label: "Endpoints", count: job.tier1_result?.api?.operations ?? 0 }]
        : [{ id: "accessibility" as const, label: "Accessibility", count: a11y }]),
    ...(job.source_type === "web" ? [{ id: "flows" as const, label: "Flows", count: job.total_pages_audited }] : []),
    ...(job.source_type === "web" ? [{ id: "performance" as const, label: "Performance", count: job.tier1_result?.performance?.findings.length ?? 0 }] : []),
    { id: "cases", label: "Test cases", count: cases },
    ...(code || api ? [] : [{ id: "code" as const, label: "Automation" }]),
    { id: "changes", label: "Changes" },
    { id: "standards", label: "Standards" },
    { id: "downloads", label: "Downloads", count: job.exports.length },
  ];
  const tab = tabs.find((t) => t.id === params.get("tab"))?.id ?? "summary";

  return (
    <Layout>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 flex-col gap-2">
          <Link to="/audits" className="text-sm font-semibold text-brand-600">Scans</Link>
          {title}
          <div className="flex flex-wrap items-center gap-x-3.5 gap-y-2 text-sm text-body">
            <StatusPill status={job.status} />
            <span>{sourceName[job.source_type]}</span>
            {(job.source_type === "web" || code) && <span>{job.depth[0].toUpperCase() + job.depth.slice(1)} depth</span>}
            {job.completed_at && <span>Finished {new Date(job.completed_at).toLocaleString()}</span>}
          </div>
        </div>
        <div className="flex flex-wrap gap-2.5">
          <Link to="/scans/new" className="flex h-12 items-center rounded-[10px] border-[1.5px] border-ink bg-white px-[18px] font-semibold">New scan</Link>
          {job.exports.includes("report") && <DownloadButton id={job.id} kind="report" label="Download report" primary />}
        </div>
      </div>

      {job.status !== "completed" && (
        <p role="alert" className={`mb-6 rounded-xl border px-5 py-4 ${job.status === "failed" ? "border-red-200 bg-red-50 text-red-800" : "border-orange-200 bg-orange-50 text-orange-900"}`}>
          {job.status === "failed"
            ? "This scan could not finish. The steps below show what went wrong."
            : "Some steps failed, so these results are incomplete. The Summary tab shows which."}
        </p>
      )}

      <div role="group" aria-label="Result sections" className="mb-6 flex flex-wrap gap-1.5 rounded-[14px] border border-gray-300 bg-white p-1.5">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            aria-pressed={t.id === tab}
            onClick={() => setParams(t.id === "summary" ? {} : { tab: t.id }, { replace: true })}
            className={`flex min-h-[44px] items-center gap-2 rounded-[10px] px-4 font-semibold ${t.id === tab ? "bg-ink text-white" : "text-ink hover:bg-soft"}`}
          >
            {t.label}
            {t.count !== undefined && (
              <span className={`rounded-full px-2 text-[13px] font-bold text-ink ${t.id === tab ? "bg-white" : "bg-gray-100"}`}>{t.count}</span>
            )}
          </button>
        ))}
      </div>

      {tab === "summary" && (
        <div className="flex flex-col gap-6">
          <dl className="grid overflow-hidden rounded-2xl border-2 border-ink bg-white shadow-hard sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Risk score" value={job.risk_score ?? "None"} note="0 is safest, 100 is worst" bad={(job.risk_score ?? 0) >= 60} />
            <Stat label="Security findings" value={findings.length} note={`${job.critical_count} critical, ${job.high_count} high`} bad={job.critical_count > 0} />
            {code ? (
              <>
                <Stat label="Files read" value={job.total_pages_audited} note={languages.slice(0, 3).join(", ") || "No source files"} />
                <Stat
                  label="Routes without tests"
                  value={gaps ? gaps.untested_route_count : "None"}
                  note={gaps ? `of ${gaps.route_count} found, ${gaps.untested_file_count} files without tests` : "Not measured"}
                  bad={!!gaps && gaps.route_count > 0 && gaps.untested_route_count / gaps.route_count > 0.5}
                />
              </>
            ) : (
              <>
                {api ? (
                  <Stat label="Endpoints read" value={job.total_pages_audited} note={`${job.tier1_result?.api?.secured ?? 0} need sign-in`} />
                ) : (
                  <Stat label="Pages mapped" value={job.total_pages_audited} note={`${a11y} accessibility ${a11y === 1 ? "problem" : "problems"}`} />
                )}
                <Stat label="Manual test cases" value={cases} note={job.exports.includes("playwright") || job.exports.includes("appium") ? "plus automation scripts" : "no automation in this scan"} />
              </>
            )}
          </dl>

          {job.tier1_result?.sign_in && (
            <p role="status" className={`rounded-xl border px-5 py-3 ${job.tier1_result.sign_in === "ok" ? "border-emerald-200 bg-emerald-50 text-emerald-900" : "border-orange-200 bg-orange-50 text-orange-900"}`}>
              {job.tier1_result.sign_in === "ok"
                ? "Wiseflow signed in with the details you gave, so pages behind the login are included."
                : `Signing in did not work, so only public pages were scanned. ${job.tier1_result.sign_in}.`}
            </p>
          )}

          {job.executive_summary && (
            <section className="rounded-2xl border border-gray-300 bg-white p-6">
              <h2 className="mb-3 text-lg font-bold">Summary for leadership</h2>
              <div className="flex max-w-[70ch] flex-col gap-3">
                {job.executive_summary.split(/\n{2,}/).map((p, i) => (
                  <p key={i}>{p}</p>
                ))}
              </div>
            </section>
          )}

          {findings.length > 0 && (
            <section className="overflow-hidden rounded-2xl border border-gray-300 bg-white">
              <h2 className="px-5 py-4 text-lg font-bold">Fix these first</h2>
              <ul>
                {findings.slice(0, 5).map((f, i) => (
                  <li key={i} className="flex flex-wrap items-center gap-x-3.5 gap-y-2 border-t border-line px-5 py-3.5">
                    <SeverityTag severity={f.severity} />
                    <span className="min-w-0 flex-[1_1_240px] font-semibold">{f.title}</span>
                    <span className="break-all font-mono text-[13px] text-body">{f.affected_url}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <div className="flex flex-col gap-3">
            <h2 className="text-lg font-bold">What ran</h2>
            <StepList job={job} />
          </div>
        </div>
      )}
      {tab === "security" && <SecurityTab job={job} />}
      {tab === "accessibility" && <AccessibilityTab job={job} />}
      {tab === "gaps" && <QaGapsTab job={job} />}
      {tab === "cases" && <TestCasesTab job={job} />}
      {tab === "code" && <AutomationTab job={job} />}
      {tab === "flows" && <FlowsTab job={job} />}
      {tab === "performance" && <PerformanceTab job={job} />}
      {tab === "endpoints" && <EndpointsTab job={job} />}
      {tab === "changes" && <ChangesTab job={job} />}
      {tab === "standards" && <StandardsTab job={job} />}
      {tab === "downloads" && <DownloadsTab job={job} />}
    </Layout>
  );
}
