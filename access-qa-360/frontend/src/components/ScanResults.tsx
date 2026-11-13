import { useEffect, useMemo, useState } from "react";
import { Copy, Download } from "lucide-react";
import type { AuditJob, ExportKind, Finding, ManualCase } from "../api/audits";
import { exportPath, isCode } from "../api/audits";
import { downloadFromApi } from "../utils/download";
import { createIssue, getIssues, getJira } from "../api/integrations";
import type { TrackerIssue } from "../api/integrations";
import { useCan } from "../hooks/useMe";
import { apiError } from "../utils/errors";

const severityOrder = ["critical", "high", "medium", "low", "info", "informational"];
const rank = (s: string) => {
  const i = severityOrder.indexOf(s.toLowerCase());
  return i === -1 ? severityOrder.length : i;
};

function severityClass(severity: string): string {
  switch (severity.toLowerCase()) {
    case "critical":
    case "serious":
      return "bg-red-700 text-white";
    case "high":
      return "bg-orange-100 text-orange-900";
    case "medium":
    case "moderate":
      return "bg-yellow-100 text-yellow-900";
    default:
      return "bg-gray-100 text-gray-800";
  }
}

export function SeverityTag({ severity }: { severity: string }) {
  return (
    <span className={`inline-block whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-bold capitalize ${severityClass(severity)}`}>
      {severity || "unknown"}
    </span>
  );
}

/** Every security finding of a scan, worst first: web and API checks plus mobile build checks. */
export function allFindings(job: AuditJob): Finding[] {
  const web = (job.tier3_result?.findings ?? []).map((f, index) => ({ ...f, ref: { source: "security" as const, index } }));
  const mobile = (job.tier2_result?.security_flags ?? []).map((f, index) => ({
    ...f,
    ref: { source: "mobile" as const, index },
    description: f.description ?? f.detail,
    affected_url: f.affected_url ?? job.source_filename ?? "Mobile build",
  }));
  return [...web, ...mobile].sort((a, b) => rank(a.severity) - rank(b.severity));
}

export function DownloadButton({ id, kind, label, primary }: { id: string; kind: ExportKind; label: string; primary?: boolean }) {
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const run = async () => {
    setBusy(true);
    setFailed(false);
    try {
      await downloadFromApi(exportPath(id, kind), `wiseflow-${kind}`);
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };
  return (
    <span className="inline-flex flex-col items-start gap-1">
      <button
        type="button"
        onClick={run}
        disabled={busy}
        className={`flex h-11 items-center gap-2 whitespace-nowrap rounded-[10px] px-4 text-sm font-semibold disabled:opacity-60 ${
          primary ? "bg-brand-600 text-white hover:bg-brand-700" : "border-[1.5px] border-ink bg-white text-ink"
        }`}
      >
        <Download className="h-4 w-4" aria-hidden="true" />
        {busy ? "Preparing" : label}
      </button>
      {failed && <span role="alert" className="text-[13px] text-red-800">Download failed. Try again.</span>}
    </span>
  );
}

const card = "overflow-hidden rounded-2xl border border-gray-300 bg-white";
const empty = "rounded-2xl border border-gray-300 bg-white px-6 py-10 text-center text-body";
const sub = "text-[13px] font-semibold text-body";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <h3 className={sub}>{label}</h3>
      {children}
    </div>
  );
}

function Proof({ text }: { text: string }) {
  return <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded-[10px] bg-ink px-3.5 py-3 font-mono text-[13px] leading-relaxed text-gray-100">{text}</pre>;
}

/** A list on the left, the selected item's detail on the right. */
function MasterDetail<T>({ items, row, detail, label }: { items: T[]; row: (item: T) => React.ReactNode; detail: (item: T) => React.ReactNode; label: string }) {
  const [index, setIndex] = useState(0);
  const current = items[Math.min(index, items.length - 1)];
  return (
    <div className="flex flex-wrap items-start gap-6">
      <ul aria-label={label} className={`${card} max-h-[640px] min-w-0 flex-[1_1_340px] overflow-y-auto`}>
        {items.map((item, i) => (
          <li key={i} className={i === 0 ? "" : "border-t border-line"}>
            <button
              type="button"
              aria-pressed={i === index}
              onClick={() => setIndex(i)}
              className={`flex w-full flex-col gap-1.5 px-[18px] py-3.5 text-left ${i === index ? "bg-brand-50" : "bg-white hover:bg-soft"}`}
            >
              {row(item)}
            </button>
          </li>
        ))}
      </ul>
      <article className="min-w-0 flex-[999_1_440px] rounded-2xl border-2 border-ink bg-white p-6 shadow-hard-ink">{detail(current)}</article>
    </div>
  );
}

/** "Create Jira issue" for one finding, or the link to the issue it already has. */
function JiraAction({ auditId, finding, issue, connected, onCreated }: { auditId: string; finding: Finding; issue?: TrackerIssue; connected: boolean; onCreated: (issue: TrackerIssue) => void }) {
  const canCreate = useCan("scan.run");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // The detail pane is reused for every finding; forget the last finding's error.
  useEffect(() => setError(""), [finding.ref?.source, finding.ref?.index]);

  if (issue) {
    return (
      <a href={issue.issue_url} target="_blank" rel="noreferrer" className="self-start font-semibold text-brand-600 hover:text-brand-700">
        Jira issue {issue.issue_key}
      </a>
    );
  }
  if (!connected || !canCreate || !finding.ref) return null;
  const { source, index } = finding.ref;
  const create = async () => {
    setError("");
    setBusy(true);
    try {
      onCreated((await createIssue(auditId, source, index)).data);
    } catch (e) {
      setError(apiError(e, "The Jira issue could not be created. Try again."));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="flex flex-col items-start gap-1.5">
      <button type="button" onClick={create} disabled={busy} className="h-11 rounded-[10px] border-[1.5px] border-ink bg-white px-4 text-sm font-semibold disabled:opacity-60">
        {busy ? "Creating in Jira" : "Create Jira issue"}
      </button>
      {error && <span role="alert" className="text-[13.5px] text-red-800">{error}</span>}
    </div>
  );
}

export function SecurityTab({ job }: { job: AuditJob }) {
  const findings = useMemo(() => allFindings(job), [job]);
  const [issues, setIssues] = useState<Record<string, TrackerIssue>>({});
  const [jiraConnected, setJiraConnected] = useState(false);
  useEffect(() => {
    getJira().then((r) => setJiraConnected(r.data.connected)).catch(() => {});
    getIssues(job.id)
      .then((r) => setIssues(Object.fromEntries(r.data.map((i) => [i.finding_ref, i]))))
      .catch(() => {});
  }, [job.id]);
  const refOf = (f: Finding) => (f.ref ? `${f.ref.source}:${f.ref.index}` : "");
  const skipped = job.tier3_result?.skipped && !job.tier2_result?.security_flags?.length;
  if (job.tier3_result?.error && findings.length === 0) {
    return <p role="alert" className={`${empty} text-red-800`}>The security checks failed: {job.tier3_result.error}</p>;
  }
  const code = isCode(job);
  const deps = job.tier3_result?.dependencies;
  // Say plainly what the dependency lookup did, so "no findings" is not read as "all clear" when it did not run.
  const depNote =
    code && deps
      ? deps.status === "unavailable"
        ? deps.reason
        : deps.status === "none"
          ? "No dependency lists with exact versions were found, so dependencies were not checked."
          : `${deps.packages_checked} dependencies checked against the OSV vulnerability database, ${deps.vulnerable} with known vulnerabilities.${deps.reason ? ` ${deps.reason}` : ""}`
      : null;
  const note = depNote && (
    <p role={deps?.status === "unavailable" ? "alert" : undefined} className={`rounded-xl border px-5 py-3 ${deps?.status === "unavailable" ? "border-orange-200 bg-orange-50 text-orange-900" : "border-gray-300 bg-white text-body"}`}>
      {depNote}
    </p>
  );
  if (findings.length === 0) {
    return (
      <div className="flex flex-col gap-5">
        {note}
        <p className={empty}>{skipped ? "A security audit was not part of this scan." : "No security issues were found by the checks that ran."}</p>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-5">
    {note}
    <MasterDetail
      label="Findings"
      items={findings}
      row={(f) => (
        <>
          <span className="flex items-center gap-2.5">
            <SeverityTag severity={f.severity} />
            <span className="font-semibold">{f.title}</span>
          </span>
          {f.affected_url && <span className="break-all font-mono text-[13px] text-body">{f.affected_url}</span>}
          {issues[refOf(f)] && <span className="text-[13px] font-semibold text-brand-700">In Jira as {issues[refOf(f)].issue_key}</span>}
        </>
      )}
      detail={(f) => (
        <div className="flex flex-col gap-[18px]">
          <div className="flex flex-col gap-2">
            <div className="flex flex-wrap items-center gap-2.5">
              <SeverityTag severity={f.severity} />
              <span className="text-[13.5px] text-body">{[f.owasp_category, f.cwe_id].filter(Boolean).join(", ")}</span>
            </div>
            <h2 className="text-[22px] font-bold leading-tight">{f.title}</h2>
          </div>
          <JiraAction
            auditId={job.id}
            finding={f}
            issue={issues[refOf(f)]}
            connected={jiraConnected}
            onCreated={(issue) => setIssues((all) => ({ ...all, [issue.finding_ref]: issue }))}
          />
          {f.affected_url && (
            <Field label="Where">
              <span className="break-all font-mono text-sm">{[f.method, f.affected_url].filter(Boolean).join(" ")}</span>
            </Field>
          )}
          {f.description && (
            <Field label="What we found">
              <p>{f.description}</p>
            </Field>
          )}
          {(f.proof_request || f.proof_response) && (
            <Field label={f.check === "dependency" ? "Advisories" : code ? "The line" : "Proof"}>
              <Proof text={[f.proof_request, f.proof_response].filter(Boolean).join("\n\n")} />
            </Field>
          )}
          {f.remediation && (
            <Field label="How to fix it">
              <p>{f.remediation}</p>
            </Field>
          )}
        </div>
      )}
    />
    </div>
  );
}

/** Source code scans: routes and files that no test refers to. */
export function QaGapsTab({ job }: { job: AuditJob }) {
  const gaps = job.tier1_result?.qa_gaps;
  if (!gaps) return <p className={empty}>Missing tests are measured on source code scans. This scan did not read any code.</p>;
  const th = "px-5 py-2.5 font-semibold";
  return (
    <div className="flex flex-col gap-6">
      <dl className="grid overflow-hidden rounded-2xl border border-gray-300 bg-white sm:grid-cols-3">
        {[
          ["Routes without tests", `${gaps.untested_route_count} of ${gaps.route_count}`],
          ["Source files without tests", `${gaps.untested_file_count} of ${gaps.source_files}`],
          ["Test files found", String(gaps.test_files)],
        ].map(([label, value]) => (
          <div key={label} className="border-b border-line px-6 py-5 last:border-b-0 sm:border-b-0 sm:border-r sm:last:border-r-0">
            <dt className="text-sm font-semibold text-body">{label}</dt>
            <dd className="text-[28px] font-extrabold leading-tight">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="max-w-[75ch] text-body">
        A route or file counts as tested when a test file names it or refers to it. The tests were not run, so this
        shows where tests are missing, not how thorough the existing ones are.
        {job.tier1_result?.truncated ? " The file limit for this depth was reached, so part of the project was not read." : ""}
      </p>

      <section className={card}>
        <h2 className="px-5 py-4 text-lg font-bold">Routes no test refers to</h2>
        {gaps.untested_routes.length === 0 ? (
          <p className="border-t border-line px-5 py-4 text-body">
            {gaps.route_count === 0 ? "No HTTP routes were recognised in this code." : "Every route found is referred to by a test."}
          </p>
        ) : (
          <div className="relative overflow-x-auto">
            <table className="w-full min-w-[560px] border-collapse text-left">
              <thead>
                <tr className="bg-soft text-[13.5px] text-body">
                  <th scope="col" className={th}>Route</th>
                  <th scope="col" className={th}>Defined in</th>
                </tr>
              </thead>
              <tbody>
                {gaps.untested_routes.map((r, i) => (
                  <tr key={i} className="border-t border-line">
                    <td className="break-all px-5 py-3 font-mono text-sm">
                      {r.method !== "ANY" && <span className="mr-2 font-bold">{r.method}</span>}
                      {r.path}
                    </td>
                    <td className="break-all px-5 py-3 font-mono text-[13px] text-body">{r.file}:{r.line}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {gaps.untested_route_count > gaps.untested_routes.length && (
          <p className="border-t border-line px-5 py-3 text-[13.5px] text-body">Showing the first {gaps.untested_routes.length}. The full results download has them all.</p>
        )}
      </section>

      <section className={card}>
        <h2 className="px-5 py-4 text-lg font-bold">Largest files without tests</h2>
        {gaps.untested_files.length === 0 ? (
          <p className="border-t border-line px-5 py-4 text-body">Every source file is referred to by a test.</p>
        ) : (
          <div className="relative overflow-x-auto">
            <table className="w-full min-w-[560px] border-collapse text-left">
              <thead>
                <tr className="bg-soft text-[13.5px] text-body">
                  <th scope="col" className={th}>File</th>
                  <th scope="col" className={th}>Language</th>
                  <th scope="col" className={th}>Lines</th>
                </tr>
              </thead>
              <tbody>
                {gaps.untested_files.slice(0, 50).map((u) => (
                  <tr key={u.path} className="border-t border-line">
                    <td className="break-all px-5 py-3 font-mono text-sm">{u.path}</td>
                    <td className="px-5 py-3">{u.language}</td>
                    <td className="px-5 py-3">{u.lines}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {gaps.untested_file_count > 50 && (
          <p className="border-t border-line px-5 py-3 text-[13.5px] text-body">Showing the 50 largest of {gaps.untested_file_count}.</p>
        )}
      </section>
    </div>
  );
}

export function AccessibilityTab({ job }: { job: AuditJob }) {
  const a11y = job.tier1_result?.a11y_summary;
  if (!a11y) return <p className={empty}>Accessibility is checked on web apps. This scan did not include a web address.</p>;
  if (a11y.violations.length === 0) return <p className={empty}>No accessibility problems were found on the pages we checked.</p>;
  return (
    <section className={card}>
      <div className="relative overflow-x-auto">
        <table className="w-full min-w-[680px] border-collapse text-left">
          <thead>
            <tr className="bg-soft text-[13.5px] text-body">
              <th scope="col" className="px-5 py-2.5 font-semibold">Problem</th>
              <th scope="col" className="px-3 py-2.5 font-semibold">Impact</th>
              <th scope="col" className="px-3 py-2.5 font-semibold">Times found</th>
              <th scope="col" className="px-5 py-2.5 font-semibold">Pages</th>
            </tr>
          </thead>
          <tbody>
            {a11y.violations.map((v) => (
              <tr key={v.id} className="border-t border-line align-top">
                <td className="px-5 py-3.5">
                  <div className="font-semibold">{v.help || v.id}</div>
                  <div className="text-[13.5px] text-body">{v.description}</div>
                  {v.helpUrl && (
                    <a href={v.helpUrl} target="_blank" rel="noreferrer" className="text-[13.5px] font-semibold text-brand-600">
                      How to fix {v.id}
                    </a>
                  )}
                </td>
                <td className="px-3 py-3.5"><SeverityTag severity={v.impact} /></td>
                <td className="px-3 py-3.5">{v.occurrences}</td>
                <td className="px-5 py-3.5">{new Set(v.affected_pages).size}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function TestCasesTab({ job }: { job: AuditJob }) {
  const cases: ManualCase[] = job.tier4_result?.test_cases ?? [];
  if (cases.length === 0) {
    return <p className={empty}>{job.tier4_result?.skipped ? "Manual test cases were not part of this scan." : job.tier4_result?.note ?? "No test cases could be written for this app."}</p>;
  }
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="text-body">
          {cases.length === 1 ? "1 test case" : `${cases.length} test cases`}
          {job.tier4_result?.note ? `. ${job.tier4_result.note}` : ""}
        </span>
        {job.exports.includes("test-cases") && <DownloadButton id={job.id} kind="test-cases" label="Export CSV for Jira" />}
      </div>
      <MasterDetail
        label="Test cases"
        items={cases}
        row={(c) => (
          <span className="flex items-baseline gap-3">
            <span className="whitespace-nowrap font-mono text-[13px] text-body">{c.id}</span>
            <span className="min-w-0 flex-1 font-semibold">{c.title}</span>
            {c.priority && <span className="text-[13px] font-bold capitalize text-body">{c.priority}</span>}
          </span>
        )}
        detail={(c) => (
          <div className="flex flex-col gap-[18px]">
            <div className="flex flex-col gap-1.5">
              <span className="font-mono text-[13px] text-body">{[c.id, c.category, isCode(job) ? c.page_url : undefined].filter(Boolean).join(", ")}</span>
              <h2 className="text-[22px] font-bold leading-tight">{c.title}</h2>
            </div>
            {c.preconditions && (
              <Field label="Before you start">
                <p>{c.preconditions}</p>
              </Field>
            )}
            {c.steps && c.steps.length > 0 && (
              <Field label="Steps">
                <ol className="flex list-decimal flex-col gap-1.5 pl-[22px]">
                  {c.steps.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ol>
              </Field>
            )}
            {c.expected_result && (
              <div className="flex flex-col gap-1.5 rounded-[10px] bg-brand-50 px-4 py-3.5">
                <h3 className="text-[13px] font-semibold text-brand-700">Expected result</h3>
                <p>{c.expected_result}</p>
              </div>
            )}
          </div>
        )}
      />
    </div>
  );
}

export function AutomationTab({ job }: { job: AuditJob }) {
  const suites = [
    { kind: "playwright" as const, label: "Playwright, web", code: job.tier1_result?.playwright_tests ?? "" },
    { kind: "appium" as const, label: "Appium, mobile", code: job.tier2_result?.appium_tests ?? "" },
  ].filter((s) => s.code.trim());
  const [active, setActive] = useState(0);
  const [copied, setCopied] = useState(false);

  if (suites.length === 0) return <p className={empty}>Automation scripts were not part of this scan.</p>;
  const suite = suites[Math.min(active, suites.length - 1)];
  const tests = (suite.code.match(/def test_/g) ?? []).length;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(suite.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          {suites.length > 1 && (
            <div role="group" aria-label="Test suite" className="flex gap-1.5 rounded-xl border border-line bg-white p-1">
              {suites.map((s, i) => (
                <button key={s.kind} type="button" aria-pressed={i === active} onClick={() => setActive(i)} className={`min-h-[44px] rounded-[9px] px-4 text-sm font-semibold ${i === active ? "bg-ink text-white" : "text-ink"}`}>
                  {s.label}
                </button>
              ))}
            </div>
          )}
          <span className="text-body">
            {suite.label}, Python. {tests === 1 ? "1 test" : `${tests} tests`}.
          </span>
        </div>
        <div className="flex flex-wrap gap-2.5">
          <button type="button" onClick={copy} className="flex h-11 items-center gap-2 rounded-[10px] border-[1.5px] border-ink bg-white px-4 text-sm font-semibold">
            <Copy className="h-4 w-4" aria-hidden="true" />
            {copied ? "Copied" : "Copy code"}
          </button>
          <DownloadButton id={job.id} kind={suite.kind} label="Download file" primary />
        </div>
      </div>
      <pre className="max-h-[640px] overflow-auto rounded-2xl bg-ink px-6 py-5 font-mono text-[13.5px] leading-relaxed text-gray-100">{suite.code}</pre>
    </div>
  );
}

const downloads: { kind: ExportKind; name: string; desc: string; format: string }[] = [
  { kind: "report", name: "Audit report", desc: "Summary for leadership, then every finding with its fix", format: "PDF" },
  { kind: "test-cases", name: "Manual test cases", desc: "All cases with steps and expected results, ready to import into Jira", format: "CSV" },
  { kind: "playwright", name: "Playwright tests", desc: "Web automation for the pages we mapped", format: "Python" },
  { kind: "appium", name: "Appium tests", desc: "Mobile automation for the uploaded build", format: "Python" },
  { kind: "results", name: "Full results", desc: "Everything this scan produced, for your own tools", format: "JSON" },
];

export function DownloadsTab({ job }: { job: AuditJob }) {
  return (
    <section className={card}>
      <div className="relative overflow-x-auto">
        <table className="w-full min-w-[620px] border-collapse text-left">
          <thead>
            <tr className="bg-soft text-[13.5px] text-body">
              <th scope="col" className="px-5 py-2.5 font-semibold">File</th>
              <th scope="col" className="px-3 py-2.5 font-semibold">Format</th>
              <th scope="col" className="px-5 py-2.5 font-semibold"><span className="sr-only">Download</span></th>
            </tr>
          </thead>
          <tbody>
            {downloads.map((d) => {
              const available = job.exports.includes(d.kind);
              return (
                <tr key={d.kind} className="border-t border-line">
                  <th scope="row" className="px-5 py-3.5 font-semibold">
                    {d.name}
                    <div className="text-[13.5px] font-normal text-body">{d.desc}</div>
                  </th>
                  <td className="px-3 py-3.5 font-mono text-[13.5px]">{d.format}</td>
                  <td className="px-5 py-2 text-right">
                    {available ? <DownloadButton id={job.id} kind={d.kind} label="Download" /> : <span className="text-[13.5px] text-body">Not produced by this scan</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
