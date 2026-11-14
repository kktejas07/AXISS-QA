import { useEffect, useState } from "react";
import { Layout } from "../components/Layout";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { getContacts, markContact } from "../api/public";
import type { ContactRequest } from "../api/public";
import { card, emptyState, errorBox, pageTitle, quietButton } from "../components/ui";
import { apiError } from "../utils/errors";

/** Super admin: messages from the public contact form, the ones still waiting first. */
export function AdminContactsPage() {
  const [rows, setRows] = useState<ContactRequest[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getContacts().then((r) => setRows(r.data)).catch(() => setError("Contact requests could not be loaded. Reload the page to try again."));
  }, []);

  const mark = async (row: ContactRequest) => {
    setError("");
    try {
      const saved = (await markContact(row.id, !row.handled_at)).data;
      setRows((all) => (all ?? []).map((r) => (r.id === saved.id ? saved : r)));
    } catch (e) {
      setError(apiError(e, "That could not be saved."));
    }
  };
  const waiting = (rows ?? []).filter((r) => !r.handled_at).length;

  return (
    <Layout variant="admin">
      <h1 className={pageTitle}>Contact requests</h1>
      <p className="mb-7 mt-1 text-body">{rows ? `${waiting} waiting for a reply, ${rows.length} in all. These come from the Contact sales page.` : "Messages from the Contact sales page."}</p>
      {error && <p role="alert" className={`${errorBox} mb-5`}>{error}</p>}
      {!rows ? (
        !error && <LoadingSpinner />
      ) : rows.length === 0 ? (
        <p className={emptyState}>No one has written yet. Messages sent from the Contact sales page show up here.</p>
      ) : (
        <ul className="flex flex-col gap-4">
          {rows.map((r) => (
            <li key={r.id} className={`${card} p-5 ${r.handled_at ? "opacity-70" : ""}`}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="text-lg font-bold">{r.name}{r.company ? `, ${r.company}` : ""}</h2>
                  {/* Shown as text to select and copy: a mail link does not work for everyone. */}
                  <p className="select-all break-all font-mono text-[14px] text-brand-700">{r.email}</p>
                  <p className="mt-1 text-[14px] text-body">{r.about}, {new Date(r.created_at).toLocaleString()}</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`rounded-full px-2.5 py-1 text-[13px] font-bold ${r.handled_at ? "bg-emerald-100 text-emerald-900" : "bg-amber-100 text-amber-900"}`}>{r.handled_at ? "Replied" : "Waiting"}</span>
                  <button type="button" onClick={() => mark(r)} className={`${quietButton} h-11 px-4 text-sm`}>{r.handled_at ? "Mark as waiting" : "Mark as replied"}<span className="sr-only"> for {r.name}</span></button>
                </div>
              </div>
              <p className="mt-3 max-w-[80ch] whitespace-pre-wrap">{r.message}</p>
            </li>
          ))}
        </ul>
      )}
    </Layout>
  );
}
