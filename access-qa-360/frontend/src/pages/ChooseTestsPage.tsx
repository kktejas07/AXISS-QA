import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { ArrowRight, Check, Code2, ListChecks, ShieldCheck, Smartphone } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Layout } from "../components/Layout";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ScanSteps } from "../components/ScanSteps";
import { getAudit, isCode, sourceName, startAudit } from "../api/audits";
import type { AuditJob, Depth, OutputKind } from "../api/audits";
import { apiError } from "../utils/errors";

const outputInfo: Record<OutputKind, { label: string; desc: string; get: string; icon: LucideIcon; why: string }> = {
  security: {
    label: "Security audit",
    desc: "Vulnerabilities ranked by severity, each with proof and a fix.",
    get: "You get: findings and a PDF report",
    icon: ShieldCheck,
    why: "",
  },
  manual: {
    label: "Manual test cases",
    desc: "Preconditions, steps and expected results a tester can follow.",
    get: "You get: a list to read here and a CSV for Jira",
    icon: ListChecks,
    why: "",
  },
  playwright: {
    label: "Web automation, Playwright",
    desc: "Ready-to-run Playwright tests for the pages we find.",
    get: "You get: a Python test file",
    icon: Code2,
    why: "Needs a web address",
  },
  appium: {
    label: "Mobile automation, Appium",
    desc: "An Appium test suite for the uploaded build.",
    get: "You get: a Python test file",
    icon: Smartphone,
    why: "Needs an .apk or .ipa upload",
  },
};

const order: OutputKind[] = ["security", "manual", "playwright", "appium"];

const depths: { id: Depth; label: string; note: string; codeNote: string }[] = [
  { id: "quick", label: "Quick", note: "Up to 10 pages, one level of links. Fastest.", codeNote: "Up to 800 files and 150 dependencies. Fastest." },
  { id: "standard", label: "Standard", note: "Up to 40 pages, three levels of links.", codeNote: "Up to 4,000 files and 600 dependencies." },
  { id: "deep", label: "Deep", note: "Up to 80 pages, four levels of links. Takes longest.", codeNote: "Up to 12,000 files and 1,500 dependencies." },
];

// Source code scans read the code instead of visiting the app, so two outputs mean something different.
const codeInfo: Partial<Record<OutputKind, { desc: string; why?: string }>> = {
  security: { desc: "Leaked secrets, risky code and dependencies with known vulnerabilities, each with its file and line." },
  manual: { desc: "Test cases for the routes found in the code, untested routes first." },
  playwright: { desc: "", why: "Needs a running web address" },
  appium: { desc: "", why: "Needs an .apk or .ipa upload" },
};


/** Step 2 of a scan: choose the outputs, confirm permission and start. */
export function ChooseTestsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<AuditJob | null>(null);
  const [missing, setMissing] = useState(false);
  const [picked, setPicked] = useState<Set<OutputKind>>(new Set());
  const [depth, setDepth] = useState<Depth>("standard");
  const [confirmed, setConfirmed] = useState(false);
  const [signIn, setSignIn] = useState({ on: false, url: "", username: "", password: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    getAudit(id)
      .then((r) => {
        setJob(r.data);
        setPicked(new Set(r.data.allowed_outputs));
      })
      .catch(() => setMissing(true));
  }, [id]);

  if (missing) {
    return (
      <Layout>
        <h1 className="mb-4 text-4xl font-extrabold tracking-tight">Scan not found</h1>
        <Link to="/scans/new" className="font-semibold text-brand-600">Start a new scan</Link>
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
  if (job.started_at) return <Navigate to={`/audits/${job.id}`} replace />;

  const toggle = (kind: OutputKind) =>
    setPicked((prev) => {
      const next = new Set(prev);
      if (next.has(kind)) next.delete(kind);
      else next.add(kind);
      return next;
    });

  const ready = picked.size > 0 && confirmed && !busy && (!signIn.on || (signIn.url.trim() !== "" && signIn.username !== "" && signIn.password !== ""));
  const code = isCode(job);

  const start = async () => {
    setError("");
    setBusy(true);
    try {
      const login = signIn.on ? { url: signIn.url.trim(), username: signIn.username, password: signIn.password } : undefined;
      await startAudit(job.id, { outputs: order.filter((o) => picked.has(o)), depth, ownership_confirmed: confirmed, login });
      navigate(`/audits/${job.id}`);
    } catch (err) {
      setError(apiError(err, "The scan could not start. Try again."));
      setBusy(false);
    }
  };

  return (
    <Layout>
      <div className="mb-7 flex flex-col gap-5">
        <h1 className="text-4xl font-extrabold tracking-tight">What do you want from this scan?</h1>
        <ScanSteps current={2} />
      </div>

      <section aria-label="App to test" className="mb-7 flex flex-wrap items-center justify-between gap-x-8 gap-y-3 rounded-2xl border-2 border-ink bg-white px-6 py-5 shadow-hard">
        <div className="min-w-0">
          <div className="text-[13.5px] font-semibold text-body">You are testing</div>
          <div className="break-all font-mono text-[17px] font-medium">{job.target_url ?? job.repo_url ?? job.source_filename ?? job.label}</div>
        </div>
        <dl className="flex flex-wrap gap-x-9 gap-y-2">
          <div>
            <dd className="text-xl font-bold">{sourceName[job.source_type]}</dd>
            <dt className="text-[13px] text-body">Type</dt>
          </div>
          {job.app_name && (
            <div>
              <dd className="text-xl font-bold">{job.app_name}</dd>
              <dt className="text-[13px] text-body">Name</dt>
            </div>
          )}
        </dl>
      </section>

      <div className="flex flex-wrap items-start gap-7">
        <div className="flex min-w-0 flex-[999_1_520px] flex-col gap-3.5">
          <h2 className="text-lg font-bold">Outputs</h2>
          <div role="group" aria-label="Outputs" className="grid gap-3.5 sm:grid-cols-2">
            {order.map((kind) => {
              const base = outputInfo[kind];
              const over = code ? codeInfo[kind] : undefined;
              const { label, get, icon: Icon } = base;
              const desc = over?.desc || base.desc;
              const why = over?.why ?? base.why;
              const allowed = job.allowed_outputs.includes(kind);
              const on = allowed && picked.has(kind);
              return (
                <button
                  key={kind}
                  type="button"
                  disabled={!allowed}
                  aria-pressed={on}
                  onClick={() => toggle(kind)}
                  className={`flex items-start gap-3.5 rounded-[14px] border-2 p-[18px] text-left disabled:cursor-not-allowed disabled:opacity-60 ${
                    on ? "border-brand-600 bg-brand-50" : "border-gray-300 bg-white"
                  }`}
                >
                  <span
                    className={`mt-px flex h-6 w-6 flex-none items-center justify-center rounded-[7px] border-2 ${
                      on ? "border-brand-600 bg-brand-600 text-white" : "border-gray-400 bg-white"
                    }`}
                  >
                    {on && <Check className="h-3.5 w-3.5" strokeWidth={3.2} aria-hidden="true" />}
                  </span>
                  <span className="flex min-w-0 flex-col gap-1.5">
                    <span className="flex items-center gap-2 font-bold">
                      <Icon className="h-[18px] w-[18px] text-brand-600" aria-hidden="true" />
                      {label}
                    </span>
                    <span className="text-sm text-body">{desc}</span>
                    <span className="text-[13px] font-semibold">{allowed ? get : why}</span>
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        <aside aria-label="Your scan" className="flex min-w-0 flex-[1_1_300px] flex-col gap-5 rounded-2xl border border-gray-300 bg-white p-6">
          <h2 className="text-[17px] font-bold">Your scan</h2>

          <div className="flex flex-col gap-2">
            <span className="text-[13.5px] font-semibold text-body">
              {picked.size === 1 ? "1 output" : `${picked.size} outputs`}
            </span>
            {picked.size === 0 ? (
              <p className="text-body">Pick at least one output to start.</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {order.filter((o) => picked.has(o)).map((o) => (
                  <li key={o} className="flex items-center gap-2 font-medium">
                    <Check className="h-4 w-4 text-brand-600" strokeWidth={2.8} aria-hidden="true" />
                    {outputInfo[o].label}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {(job.source_type === "web" || code) && (
            <div className="flex flex-col gap-2.5 border-t border-line pt-4">
              <span className="text-[13.5px] font-semibold text-body">Depth</span>
              <div role="group" aria-label="Depth" className="flex gap-1.5 rounded-xl border border-line bg-soft p-1">
                {depths.map((d) => (
                  <button
                    key={d.id}
                    type="button"
                    aria-pressed={depth === d.id}
                    onClick={() => setDepth(d.id)}
                    className={`min-h-[44px] flex-1 rounded-[9px] text-sm font-semibold ${depth === d.id ? "bg-ink text-white" : "text-ink"}`}
                  >
                    {d.label}
                  </button>
                ))}
              </div>
              <span className="text-[13.5px] text-body">{depths.find((d) => d.id === depth)?.[code ? "codeNote" : "note"]}</span>
            </div>
          )}

          {job.source_type === "web" && (
            <div className="flex flex-col gap-3 border-t border-line pt-4">
              <label className="flex items-start gap-3 font-medium">
                <input type="checkbox" checked={signIn.on} onChange={(e) => setSignIn({ ...signIn, on: e.target.checked })} className="mt-0.5 h-5 w-5 flex-none accent-brand-600" />
                <span>
                  Sign in first, to scan the pages behind the login
                  <span className="block text-[13.5px] font-normal text-body">Use a test account, never a real customer's. The details are stored encrypted and deleted when the scan ends.</span>
                </span>
              </label>
              {signIn.on && (
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="flex flex-col gap-1.5 text-sm font-semibold sm:col-span-2">
                    Sign-in page
                    <input type="url" value={signIn.url} onChange={(e) => setSignIn({ ...signIn, url: e.target.value })} placeholder={`${(job.target_url ?? "").replace(/\/$/, "")}/login`}
                      className="h-12 rounded-[10px] border border-gray-400 bg-white px-3.5 font-mono text-[15px]" />
                    <span className="text-[13.5px] font-normal text-body">Must be on the site being scanned.</span>
                  </label>
                  <label className="flex flex-col gap-1.5 text-sm font-semibold">
                    Email or username
                    <input value={signIn.username} onChange={(e) => setSignIn({ ...signIn, username: e.target.value })} autoComplete="off" className="h-12 rounded-[10px] border border-gray-400 bg-white px-3.5 text-[15px]" />
                  </label>
                  <label className="flex flex-col gap-1.5 text-sm font-semibold">
                    Password
                    <input type="password" value={signIn.password} onChange={(e) => setSignIn({ ...signIn, password: e.target.value })} autoComplete="new-password" className="h-12 rounded-[10px] border border-gray-400 bg-white px-3.5 text-[15px]" />
                  </label>
                </div>
              )}
            </div>
          )}

          <label className="flex items-start gap-3 border-t border-line pt-4 font-medium">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
              className="mt-0.5 h-5 w-5 flex-none accent-brand-600"
            />
            {code ? "I own this code or have written permission to review it." : "I own this app or have written permission to test it."}
          </label>

          {error && (
            <p role="alert" className="rounded-[10px] border border-red-200 bg-red-50 px-4 py-3 text-red-800">
              {error}
            </p>
          )}

          <div className="flex flex-col gap-2.5">
            <button
              type="button"
              disabled={!ready}
              onClick={start}
              className="flex h-14 items-center justify-center gap-2.5 rounded-xl bg-brand-600 text-[17px] font-bold text-white hover:bg-brand-700 disabled:bg-line disabled:text-body"
            >
              {busy ? "Starting" : "Start scan"}
              {!busy && <ArrowRight className="h-[18px] w-[18px]" strokeWidth={2.4} aria-hidden="true" />}
            </button>
            <Link to="/scans/new" className="flex min-h-[44px] items-center justify-center font-semibold text-ink">
              Start over
            </Link>
          </div>
        </aside>
      </div>
    </Layout>
  );
}
