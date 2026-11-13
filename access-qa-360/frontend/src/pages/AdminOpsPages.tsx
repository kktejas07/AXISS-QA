import { useEffect, useState } from "react";
import { Layout } from "../components/Layout";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { adminStopScan, getAiUsage, getHealth, getQueue } from "../api/admin";
import type { AiUsage, Health, QueueRow, UsageBucket } from "../api/admin";
import { apiError } from "../utils/errors";

const card = "overflow-hidden rounded-2xl border border-gray-300 bg-white";
const th = "px-4 py-2.5 font-semibold";
const title = "text-4xl font-extrabold tracking-tight";
const sourceName: Record<string, string> = { web: "Web app", android: "Android build", ios: "iOS build", code: "Source code", repo: "Repository" };

function Failed({ name }: { name: string }) {
  return (
    <Layout variant="admin">
      <h1 className={`${title} mb-7`}>{name}</h1>
      <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-red-800">This could not be loaded. Check that the API is running, then reload the page.</p>
    </Layout>
  );
}

function Stat({ label, value, note, bad }: { label: string; value: string | number; note?: string; bad?: boolean }) {
  return (
    <div className="flex flex-col gap-1 border-b border-line px-6 py-5 last:border-b-0 sm:border-b-0 sm:border-r sm:last:border-r-0">
      <dt className="text-sm font-semibold text-body">{label}</dt>
      <dd className={`text-[34px] font-extrabold leading-tight ${bad ? "text-red-700" : ""}`}>{value}</dd>
      {note && <span className="text-[13.5px] text-body">{note}</span>}
    </div>
  );
}

const ago = (iso: string | null) => {
  if (!iso) return "";
  const minutes = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  return minutes < 1 ? "just now" : minutes < 60 ? `${minutes} min ago` : `${Math.round(minutes / 60)} h ago`;
};

/** Scans running across every organisation, with a way to stop one. */
export function AdminQueuePage() {
  const [data, setData] = useState<{ active: QueueRow[]; failed_last_24h: QueueRow[]; completed_last_24h: number } | null>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    const load = () =>
      getQueue()
        .then((r) => alive && setData(r.data))
        .catch(() => alive && setFailed(true));
    load();
    const timer = setInterval(load, 5000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  const stop = async (row: QueueRow) => {
    setError("");
    setBusy(row.id);
    try {
      await adminStopScan(row.id);
      setData((await getQueue()).data);
    } catch (e) {
      setError(apiError(e, "The scan could not be stopped."));
    } finally {
      setBusy(null);
    }
  };

  if (failed) return <Failed name="Scan queue" />;
  const stale = data?.active.filter((r) => !r.alive).length ?? 0;

  return (
    <Layout variant="admin">
      <h1 className={title}>Scan queue</h1>
      <p className="mb-7 mt-1 text-body">Scans running now across every organisation. This page refreshes every few seconds.</p>
      {!data ? (
        <LoadingSpinner />
      ) : (
        <>
          <dl className="mb-7 grid overflow-hidden rounded-2xl border-2 border-ink bg-white shadow-hard-ink sm:grid-cols-3">
            <Stat label="Running now" value={data.active.length} note={stale ? `${stale} not making progress` : "all making progress"} bad={stale > 0} />
            <Stat label="Finished in the last 24 hours" value={data.completed_last_24h} />
            <Stat label="Failed or incomplete, last 24 hours" value={data.failed_last_24h.length} bad={data.failed_last_24h.length > 0} />
          </dl>
          {error && <p role="alert" className="mb-5 rounded-xl border border-red-200 bg-red-50 px-5 py-3 text-red-800">{error}</p>}

          <section className={`${card} mb-7`}>
            <h2 className="px-5 py-4 text-lg font-bold">Running now</h2>
            {data.active.length === 0 ? (
              <p className="border-t border-line px-5 py-4 text-body">No scans are running.</p>
            ) : (
              <div className="relative overflow-x-auto">
                <table className="w-full min-w-[860px] border-collapse text-left">
                  <thead>
                    <tr className="bg-soft text-[13.5px] text-body">
                      <th scope="col" className={th}>Scan</th>
                      <th scope="col" className={th}>Organisation</th>
                      <th scope="col" className={th}>Progress</th>
                      <th scope="col" className={th}>Started</th>
                      <th scope="col" className={th}><span className="sr-only">Actions</span></th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.active.map((r) => (
                      <tr key={r.id} className="border-t border-line align-top">
                        <td className="px-4 py-3">
                          <div className="break-all font-mono text-sm font-medium">{r.label}</div>
                          <div className="text-[13.5px] text-body">{sourceName[r.source_type] ?? r.source_type}</div>
                        </td>
                        <td className="px-4 py-3">
                          <div>{r.organization ?? "None"}</div>
                          <div className="break-all text-[13.5px] text-body">{r.started_by}</div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="font-semibold">{r.progress}%{r.step ? `, ${r.step.toLowerCase()}` : ""}</div>
                          {!r.alive && <div className="text-[13.5px] font-semibold text-red-800">Not making progress. The server restarted while it ran; stop it to clear it.</div>}
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-body">{ago(r.started_at)}</td>
                        <td className="px-4 py-2 text-right">
                          <button type="button" disabled={busy === r.id} onClick={() => stop(r)} aria-label={`Stop the scan of ${r.label}`} className="h-11 rounded-[10px] border-[1.5px] border-red-700 bg-white px-3.5 text-sm font-semibold text-red-800 disabled:opacity-50">
                            {busy === r.id ? "Stopping" : "Stop"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className={card}>
            <h2 className="px-5 py-4 text-lg font-bold">Failed or incomplete in the last 24 hours</h2>
            {data.failed_last_24h.length === 0 ? (
              <p className="border-t border-line px-5 py-4 text-body">Nothing failed.</p>
            ) : (
              <ul>
                {data.failed_last_24h.map((r) => (
                  <li key={r.id} className="flex flex-col gap-1 border-t border-line px-5 py-3.5">
                    <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
                      <span className="break-all font-mono text-sm font-medium">{r.label}</span>
                      <span className="text-[13.5px] text-body">{r.organization ?? "No organisation"}, {ago(r.completed_at)}</span>
                    </div>
                    <span className="break-words text-[14.5px] text-red-800">{r.problem ?? (r.status === "partial" ? "Some steps failed" : "Stopped or failed without a recorded reason")}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </Layout>
  );
}

const money = (n: number) => `$${n.toFixed(2)}`;
const tokens = (n: number) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${Math.round(n / 1e3)}K` : String(n));

function UsageTable<T extends UsageBucket>({ caption, rows, name, first }: { caption: string; rows: T[]; name: (row: T) => string; first: string }) {
  return (
    <section className={card}>
      <h2 className="px-5 py-4 text-lg font-bold">{caption}</h2>
      {rows.length === 0 ? (
        <p className="border-t border-line px-5 py-4 text-body">No AI calls in this period.</p>
      ) : (
        <div className="relative overflow-x-auto">
          <table className="w-full min-w-[560px] border-collapse text-left">
            <thead>
              <tr className="bg-soft text-[13.5px] text-body">
                <th scope="col" className={th}>{first}</th>
                <th scope="col" className={`${th} text-right`}>Calls</th>
                <th scope="col" className={`${th} text-right`}>Tokens in</th>
                <th scope="col" className={`${th} text-right`}>Tokens out</th>
                <th scope="col" className={`${th} text-right`}>Estimated cost</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={name(r)} className="border-t border-line">
                  <td className="break-all px-4 py-3 font-semibold">{name(r)}</td>
                  <td className="px-4 py-3 text-right">{r.calls}{r.failed ? <span className="text-red-800"> ({r.failed} failed)</span> : null}</td>
                  <td className="px-4 py-3 text-right">{tokens(r.input_tokens)}</td>
                  <td className="px-4 py-3 text-right">{tokens(r.output_tokens)}</td>
                  <td className="px-4 py-3 text-right font-semibold">{money(r.cost)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

/** How much AI the platform is using, and roughly what it costs. */
export function AdminAiUsagePage() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState<AiUsage | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setData(null);
    getAiUsage(days)
      .then((r) => setData(r.data))
      .catch(() => setFailed(true));
  }, [days]);

  if (failed) return <Failed name="AI usage" />;
  const peak = Math.max(1, ...(data?.by_day.map((d) => d.cost) ?? []));

  return (
    <Layout variant="admin">
      <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className={title}>AI usage</h1>
          <p className="mt-1 text-body">Calls made to write test cases, scripts and summaries.</p>
        </div>
        <label className="flex flex-col gap-1.5 text-[13.5px] font-semibold text-body">
          Period
          <select value={days} onChange={(e) => setDays(Number(e.target.value))} className="h-12 rounded-[10px] border border-gray-400 bg-white px-2.5 text-[15px] text-ink">
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </label>
      </div>
      {!data ? (
        <LoadingSpinner />
      ) : (
        <div className="flex flex-col gap-7">
          {!data.ai_configured && (
            <p role="alert" className="rounded-xl border border-orange-200 bg-orange-50 px-5 py-4 text-orange-900">
              No AI service key is set on this server, so scans fall back to basic test cases and summaries.
            </p>
          )}
          <dl className="grid overflow-hidden rounded-2xl border-2 border-ink bg-white shadow-hard-ink sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Estimated cost" value={money(data.total.cost)} note="at list prices, in US dollars" />
            <Stat label="Calls" value={data.total.calls} note={`${data.total.failed} failed`} bad={data.total.failed > 0 && data.total.failed >= data.total.calls / 2} />
            <Stat label="Tokens in" value={tokens(data.total.input_tokens)} />
            <Stat label="Tokens out" value={tokens(data.total.output_tokens)} />
          </dl>
          <p className="max-w-[75ch] text-body">
            Cost is an estimate from token counts and list prices, not a bill. Check your AI provider's invoice for the real figure.
            {data.unpriced_models.length > 0 && ` No price is known for ${data.unpriced_models.join(", ")}, so those calls are counted at $0.`}
          </p>

          {data.by_day.length > 0 && (
            <section className={`${card} p-5`}>
              <h2 className="mb-4 text-lg font-bold">Estimated cost by day</h2>
              <ul className="flex flex-col gap-1.5">
                {data.by_day.map((d) => (
                  <li key={d.day} className="flex items-center gap-3 text-[14.5px]">
                    <span className="w-24 flex-none text-body">{new Date(d.day).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</span>
                    <span className="h-3 min-w-0 flex-1 overflow-hidden rounded-full bg-line">
                      <span className="block h-full bg-brand-600" style={{ width: `${(d.cost / peak) * 100}%` }} />
                    </span>
                    <span className="w-28 flex-none text-right font-semibold">{money(d.cost)}, {d.calls} calls</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <UsageTable caption="By organisation" first="Organisation" rows={data.by_organization} name={(r) => r.organization} />
          <UsageTable caption="By what it was for" first="Used for" rows={data.by_purpose} name={(r) => r.purpose} />
          <UsageTable caption="By model" first="Model" rows={data.by_model} name={(r) => r.model} />
        </div>
      )}
    </Layout>
  );
}

const healthLook = {
  ok: { text: "Working", look: "bg-emerald-100 text-emerald-800" },
  down: { text: "Down", look: "bg-red-700 text-white" },
  off: { text: "Not set up", look: "bg-gray-100 text-gray-800" },
};

/** Each part the platform depends on, checked when the page loads. */
export function AdminHealthPage() {
  const [data, setData] = useState<Health | null>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = () => {
    setBusy(true);
    return getHealth()
      .then((r) => setData(r.data))
      .catch(() => setFailed(true))
      .finally(() => setBusy(false));
  };
  useEffect(() => {
    load();
  }, []);

  if (failed) return <Failed name="System health" />;

  return (
    <Layout variant="admin">
      <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className={title}>System health</h1>
          <p className="mt-1 text-body">{data ? `Checked ${new Date(data.checked_at).toLocaleTimeString()}, ${data.environment} environment` : "Checking"}</p>
        </div>
        <button type="button" onClick={load} disabled={busy} className="h-12 rounded-[10px] border-[1.5px] border-ink bg-white px-5 font-semibold disabled:opacity-60">
          {busy ? "Checking" : "Check again"}
        </button>
      </div>
      {!data ? (
        <LoadingSpinner />
      ) : (
        <>
          <p role="status" className={`mb-6 rounded-xl border px-5 py-4 font-semibold ${data.healthy ? "border-emerald-200 bg-emerald-50 text-emerald-900" : "border-red-200 bg-red-50 text-red-800"}`}>
            {data.healthy ? "Everything Wiseflow needs is working." : "Something Wiseflow needs is down. See the parts marked Down below."}
          </p>
          <ul className={card}>
            {data.checks.map((c, i) => (
              <li key={c.name} className={`flex flex-wrap items-start justify-between gap-x-6 gap-y-2 px-5 py-4 ${i ? "border-t border-line" : ""}`}>
                <div className="min-w-0 flex-[1_1_320px]">
                  <div className="font-bold">{c.name}{!c.required && <span className="ml-2 text-[13px] font-normal text-body">Optional</span>}</div>
                  <div className="text-[14.5px] text-body">{c.detail}</div>
                </div>
                <span className={`whitespace-nowrap rounded-full px-2.5 py-1 text-[13px] font-bold ${healthLook[c.status].look}`}>{healthLook[c.status].text}</span>
              </li>
            ))}
          </ul>
          <p className="mt-4 text-[14.5px] text-body">Scans this server is working on right now: {data.scans_running_here}.</p>
        </>
      )}
    </Layout>
  );
}
