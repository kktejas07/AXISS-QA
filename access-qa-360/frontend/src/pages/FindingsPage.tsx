import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getInbox, setFindingState } from "../api/workspace";
import type { FindingStatus, Inbox, InboxItem } from "../api/workspace";
import { getMembers } from "../api/org";
import { EmptyPanel, ShieldList } from "../components/Illustrations";
import { Layout } from "../components/Layout";
import { Skeleton } from "../components/LoadingSpinner";
import { SeverityTag } from "../components/ScanResults";
import { card, errorBox, field, pageTitle } from "../components/ui";
import { useCan } from "../hooks/useMe";
import { apiError } from "../utils/errors";

const statusName: Record<FindingStatus, string> = { open: "Open", fixed: "Fixed", accepted: "Risk accepted", false_positive: "Not a problem" };
const tabFor: Record<string, string> = { accessibility: "accessibility", performance: "performance" };

/** Every finding from the latest scan of each target, with the team's decision on it. */
export function FindingsPage() {
  const canDecide = useCan("scan.run");
  const [status, setStatus] = useState<FindingStatus>("open");
  const [severity, setSeverity] = useState("");
  const [mine, setMine] = useState(false);
  const [data, setData] = useState<Inbox | null>(null);
  const [people, setPeople] = useState<{ id: string; full_name: string }[]>([]);
  const [editing, setEditing] = useState<string | null>(null);
  const [form, setForm] = useState<{ status: FindingStatus; assignee_id: string; note: string }>({ status: "open", assignee_id: "", note: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = () => getInbox({ status, severity, assignee: mine ? "me" : "" }).then((r) => setData(r.data)).catch(() => setError("The findings could not be loaded. Try again."));
  useEffect(() => { load(); }, [status, severity, mine]);
  useEffect(() => { getMembers().then((r) => setPeople(r.data)).catch(() => {}); }, []);

  const key = (i: InboxItem) => `${i.audit_id}:${i.source}:${i.index}`;
  const open = (i: InboxItem) => {
    setEditing(key(i));
    setForm({ status: i.status, assignee_id: i.assignee_id ?? "", note: i.note ?? "" });
    setError("");
    setNotice("");
  };
  const save = async (i: InboxItem) => {
    setError("");
    setBusy(true);
    try {
      await setFindingState({ audit_id: i.audit_id, source: i.source, index: i.index, status: form.status, assignee_id: form.assignee_id || null, note: form.note.trim() || null });
      setEditing(null);
      await load();
      setNotice(`“${i.title}” is now ${statusName[form.status].toLowerCase()}.`);
    } catch (e) {
      setError(apiError(e, "The change could not be saved."));
    } finally {
      setBusy(false);
    }
  };
  const needsWhy = form.status === "accepted" || form.status === "false_positive";

  return (
    <Layout>
      <h1 className={pageTitle}>Findings</h1>
      <p className="mb-6 mt-1 max-w-[66ch] text-body">Everything the latest scan of each app found, in one list. Decide what happens to each one; the decision stays with the finding on later scans.</p>
      {error && <p role="alert" className={`${errorBox} mb-5`}>{error}</p>}
      {notice && <p role="status" className="mb-5 rounded-[10px] border border-emerald-200 bg-emerald-50 px-4 py-3 text-emerald-900">{notice}</p>}

      <div className="mb-5 flex flex-wrap items-center gap-3">
        <div role="group" aria-label="Status" className="flex flex-wrap gap-1 rounded-[11px] border border-gray-300 bg-white p-1">
          {(Object.keys(statusName) as FindingStatus[]).map((s) => (
            <button key={s} type="button" aria-pressed={status === s} onClick={() => setStatus(s)} className={`min-h-[40px] rounded-[8px] px-3.5 text-sm font-semibold ${status === s ? "bg-ink text-white" : "text-ink"}`}>
              {statusName[s]}{data ? ` (${data.counts[s]})` : ""}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm font-semibold">
          Severity
          <select value={severity} onChange={(e) => setSeverity(e.target.value)} className="h-11 rounded-[10px] border border-gray-400 bg-white px-3">
            <option value="">All</option>
            {["critical", "high", "medium", "low"].map((s) => <option key={s} value={s}>{s[0].toUpperCase() + s.slice(1)}</option>)}
          </select>
        </label>
        <label className="flex min-h-[44px] items-center gap-2 text-sm font-semibold">
          <input type="checkbox" checked={mine} onChange={(e) => setMine(e.target.checked)} className="h-[18px] w-[18px] accent-brand-600" />
          Assigned to me
        </label>
      </div>

      {!data ? (
        !error && <Skeleton rows={5} className="max-w-2xl" />
      ) : data.total === 0 ? (
        <EmptyPanel art={<ShieldList />} title="No findings yet" action={<Link to="/scans/new" className="flex h-12 items-center rounded-[10px] bg-ink px-5 font-bold text-white">Start a scan</Link>}>
          Findings from your scans collect here once a scan has finished.
        </EmptyPanel>
      ) : data.items.length === 0 ? (
        <p className={`${card} px-6 py-10 text-center text-body`}>Nothing matches these filters.</p>
      ) : (
        <ul className={`${card} divide-y divide-line overflow-hidden`}>
          {data.items.map((i) => (
            <li key={key(i)} className="flex flex-col gap-2 px-5 py-3.5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex min-w-0 flex-1 flex-col gap-1">
                  <span className="flex flex-wrap items-center gap-2.5">
                    <SeverityTag severity={i.severity} />
                    <Link to={`/audits/${i.audit_id}?tab=${tabFor[i.source] ?? "security"}`} className="font-semibold hover:text-brand-700">{i.title}</Link>
                  </span>
                  <span className="break-all text-[13.5px] text-body">{i.app}{i.location && i.location !== i.app ? `, ${i.location}` : ""}</span>
                  {(i.assignee || i.note) && <span className="text-[13.5px]">{i.assignee && <span className="font-semibold">Owner: {i.assignee}. </span>}{i.note}</span>}
                </div>
                {canDecide && editing !== key(i) && (
                  <button type="button" onClick={() => open(i)} aria-label={`Decide about ${i.title}`} className="h-10 rounded-[9px] border-[1.5px] border-gray-400 bg-white px-3.5 text-sm font-semibold">Decide</button>
                )}
              </div>
              {editing === key(i) && (
                <form onSubmit={(e) => { e.preventDefault(); save(i); }} className="wf-fade-up flex flex-col gap-3 rounded-xl bg-soft p-4">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <label className="flex flex-col gap-1.5 text-sm font-semibold">
                      What happens to it
                      <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as FindingStatus })} className={field}>
                        {(Object.keys(statusName) as FindingStatus[]).map((s) => <option key={s} value={s}>{statusName[s]}</option>)}
                      </select>
                    </label>
                    <label className="flex flex-col gap-1.5 text-sm font-semibold">
                      Owner
                      <select value={form.assignee_id} onChange={(e) => setForm({ ...form, assignee_id: e.target.value })} className={field}>
                        <option value="">Nobody yet</option>
                        {people.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
                      </select>
                    </label>
                  </div>
                  <label className="flex flex-col gap-1.5 text-sm font-semibold">
                    {needsWhy ? "Why" : "Note (optional)"}
                    <input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} required={needsWhy} maxLength={500} className={field} />
                  </label>
                  <div className="flex flex-wrap gap-2.5">
                    <button type="submit" disabled={busy} className="h-11 rounded-[10px] bg-ink px-4 text-sm font-bold text-white disabled:opacity-50">{busy ? "Saving" : "Save decision"}</button>
                    <button type="button" onClick={() => setEditing(null)} className="h-11 rounded-[10px] border-[1.5px] border-ink bg-white px-4 text-sm font-semibold">Cancel</button>
                  </div>
                </form>
              )}
            </li>
          ))}
        </ul>
      )}
    </Layout>
  );
}
