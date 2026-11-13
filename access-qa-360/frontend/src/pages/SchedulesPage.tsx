import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CalendarClock as CalendarIcon, Play, Trash2 } from "lucide-react";
import { changeSchedule, createSchedule, deleteSchedule, getSchedules, runScheduleNow } from "../api/insights";
import type { Frequency, Schedule } from "../api/insights";
import { CalendarClock, EmptyPanel } from "../components/Illustrations";
import { Layout } from "../components/Layout";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { card, errorBox, field, hint, label, pageTitle, primaryButton, quietButton } from "../components/ui";
import { useCan } from "../hooks/useMe";
import { apiError } from "../utils/errors";

const every: Record<Frequency, string> = { daily: "Every day", weekly: "Every week", monthly: "Every month" };
const smallButton = "flex h-11 items-center gap-2 rounded-[10px] border-[1.5px] border-gray-400 bg-white px-3.5 text-sm font-semibold disabled:opacity-50";

/** Scans that repeat by themselves, and a form to add one. */
export function SchedulesPage() {
  const canRun = useCan("scan.run");
  const [rows, setRows] = useState<Schedule[] | null>(null);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ source_type: "web" as "web" | "repo", target: "", frequency: "weekly" as Frequency, confirmed: false });
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = () => getSchedules().then((r) => setRows(r.data)).catch(() => setError("Your schedules could not be loaded. Try again."));
  useEffect(() => { load(); }, []);

  const act = async (key: string, work: () => Promise<unknown>, done: string, failed: string) => {
    setError("");
    setNotice("");
    setBusy(key);
    try {
      await work();
      await load();
      setNotice(done);
    } catch (e) {
      setError(apiError(e, failed));
    } finally {
      setBusy("");
    }
  };

  const add = (e: React.FormEvent) => {
    e.preventDefault();
    act("add", async () => {
      await createSchedule({ source_type: form.source_type, target: form.target.trim(), frequency: form.frequency, outputs: ["security"], depth: "standard", ownership_confirmed: form.confirmed });
      setAdding(false);
      setForm({ ...form, target: "", confirmed: false });
    }, "Schedule added.", "The schedule could not be added.");
  };

  return (
    <Layout>
      <div className="mb-7 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className={pageTitle}>Schedules</h1>
          <p className="mt-1 max-w-[62ch] text-body">Re-scan a website or repository on a timetable. Each run counts as one scan, and you are told what is new or fixed since the run before.</p>
        </div>
        {canRun && !adding && (
          <button type="button" onClick={() => setAdding(true)} className={primaryButton}>
            <CalendarIcon className="h-5 w-5" aria-hidden="true" />
            Add a schedule
          </button>
        )}
      </div>
      {error && <p role="alert" className={`${errorBox} mb-5`}>{error}</p>}
      {notice && <p role="status" className="mb-5 rounded-[10px] border border-emerald-200 bg-emerald-50 px-4 py-3 text-emerald-900">{notice}</p>}

      {adding && (
        <form onSubmit={add} className={`${card} mb-6 flex flex-col gap-5 p-6`}>
          <h2 className="text-lg font-bold">New schedule</h2>
          <fieldset className="flex flex-wrap gap-2.5">
            <legend className="mb-1.5 text-sm font-semibold">What to scan</legend>
            {([["web", "A website"], ["repo", "A repository"]] as const).map(([value, text]) => (
              <label key={value} className={`flex h-12 cursor-pointer items-center gap-2.5 rounded-[10px] border-[1.5px] px-4 font-semibold ${form.source_type === value ? "border-ink bg-ink text-white" : "border-gray-400 bg-white"}`}>
                <input type="radio" name="source" className="sr-only" checked={form.source_type === value} onChange={() => setForm({ ...form, source_type: value, target: "" })} />
                {text}
              </label>
            ))}
          </fieldset>
          <div className="grid gap-4 sm:grid-cols-[1fr_220px]">
            <label className={label}>
              {form.source_type === "web" ? "Web address" : "Repository link"}
              <input type="url" required value={form.target} onChange={(e) => setForm({ ...form, target: e.target.value })} className={`${field} font-mono`}
                placeholder={form.source_type === "web" ? "https://shop.example.com" : "https://github.com/acme/shop"} />
              {form.source_type === "repo" && <span className={hint}>A public repository on GitHub, GitLab or Bitbucket.</span>}
            </label>
            <label className={label}>
              How often
              <select value={form.frequency} onChange={(e) => setForm({ ...form, frequency: e.target.value as Frequency })} className={field}>
                {(Object.keys(every) as Frequency[]).map((f) => <option key={f} value={f}>{every[f]}</option>)}
              </select>
            </label>
          </div>
          <label className="flex items-start gap-3">
            <input type="checkbox" checked={form.confirmed} onChange={(e) => setForm({ ...form, confirmed: e.target.checked })} className="mt-1 h-5 w-5 accent-brand-600" />
            <span>I own this app or have permission to test it, and that will still be true each time this runs.</span>
          </label>
          <div className="flex flex-wrap gap-2.5">
            <button type="submit" disabled={busy === "add" || !form.confirmed} className={primaryButton}>{busy === "add" ? "Adding" : "Add schedule"}</button>
            <button type="button" onClick={() => setAdding(false)} className={quietButton}>Cancel</button>
          </div>
        </form>
      )}

      {!rows ? (
        !error && <LoadingSpinner />
      ) : rows.length === 0 ? (
        !adding && (
          <EmptyPanel art={<CalendarClock />} title="No scheduled scans yet"
            action={canRun ? <button type="button" onClick={() => setAdding(true)} className={primaryButton}>Add a schedule</button> : undefined}>
            Add a website or repository and Wiseflow will scan it every day, week or month, then report what changed.
          </EmptyPanel>
        )
      ) : (
        <ul className="flex flex-col gap-4">
          {rows.map((s) => (
            <li key={s.id} className={`${card} flex flex-wrap items-center justify-between gap-4 p-5`}>
              <div className="flex min-w-0 flex-col gap-1">
                <span className="break-all font-mono font-semibold">{s.target.replace(/^https?:\/\//, "").replace(/\.git$/, "")}</span>
                <span className="text-sm text-body">
                  {every[s.frequency]}, {s.active ? `next on ${new Date(s.next_run_at).toLocaleString()}` : "paused"}
                </span>
                {s.last_note ? (
                  <span role="status" className="text-sm font-semibold text-orange-800">{s.last_note}</span>
                ) : s.last_audit_id ? (
                  <Link to={`/audits/${s.last_audit_id}?tab=changes`} className="text-sm font-semibold text-brand-600">Last run: {new Date(s.last_run_at!).toLocaleString()}</Link>
                ) : (
                  <span className="text-sm text-body">Has not run yet</span>
                )}
              </div>
              {canRun && (
                <div className="flex flex-wrap gap-2.5">
                  <button type="button" disabled={!!busy} className={smallButton}
                    onClick={() => act(s.id, () => runScheduleNow(s.id), "Scan started.", "The scan could not be started.")}>
                    <Play className="h-4 w-4" aria-hidden="true" />
                    Run now
                  </button>
                  <button type="button" disabled={!!busy} className={smallButton}
                    onClick={() => act(s.id, () => changeSchedule(s.id, { active: !s.active }), s.active ? "Schedule paused." : "Schedule resumed.", "The schedule could not be changed.")}>
                    {s.active ? "Pause" : "Resume"}
                  </button>
                  <button type="button" disabled={!!busy} className={smallButton} aria-label={`Delete the schedule for ${s.target}`}
                    onClick={() => act(s.id, () => deleteSchedule(s.id), "Schedule deleted. Scans it already ran are kept.", "The schedule could not be deleted.")}>
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                    Delete
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </Layout>
  );
}
