import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { ArrowRight, FileText, Send, Trash2, X } from "lucide-react";
import { addWiseDocument, askWise, getWiseDocuments, getWisePrompts, removeWiseDocument } from "../api/wise";
import type { WiseDocument, WiseMessage, WisePrompt } from "../api/wise";
import { apiError } from "../utils/errors";
import { WiseBot } from "./WiseBot";
import type { BotState } from "./WiseBot";
import { Dots } from "./LoadingSpinner";
import { errorBox } from "./ui";

const KEY = "wise-chat";
const saved = (): WiseMessage[] => {
  try {
    return JSON.parse(sessionStorage.getItem(KEY) ?? "[]");
  } catch {
    return [];
  }
};

/**
 * Wise, the assistant. A round button floats at the bottom right of every
 * signed-in screen; pressing it opens a chat panel. Answers come from the
 * organisation's own scans and documents, with links to where each came from.
 */
export function Wise() {
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<WiseMessage[]>(saved);
  const [prompts, setPrompts] = useState<WisePrompt[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // What the character shows: searching while it works, a moment of "done" after an answer, "error" when it failed.
  const [justAnswered, setJustAnswered] = useState(false);
  const mood: BotState = busy ? "searching" : error ? "error" : justAnswered ? "done" : open ? "listening" : "idle";
  const end = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  // On a scan's page, that scan is always among the things Wise searches.
  const auditId = /^\/audits\/([0-9a-f-]{36})/.exec(location.pathname)?.[1];

  useEffect(() => {
    if (!open) return;
    input.current?.focus();
    if (prompts.length === 0) getWisePrompts().then((r) => setPrompts(r.data)).catch(() => {});
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, prompts.length]);

  useEffect(() => {
    try {
      sessionStorage.setItem(KEY, JSON.stringify(messages.slice(-30)));
    } catch {
      /* the chat still works without being remembered */
    }
    end.current?.scrollIntoView?.({ block: "end" });
  }, [messages, busy]);

  const ask = async (text: string) => {
    const question = text.trim();
    if (!question || busy) return;
    const next: WiseMessage[] = [...messages, { role: "user", content: question }];
    setMessages(next);
    setDraft("");
    setError("");
    setBusy(true);
    try {
      const { data } = await askWise(next, auditId);
      setMessages([...next, { role: "assistant", content: data.answer, sources: data.sources, actions: data.actions }]);
      setJustAnswered(true);
      setTimeout(() => setJustAnswered(false), 2600);
    } catch (e) {
      setError(apiError(e, "Wise could not answer just now. Try again."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      {open && (
        <section
          role="dialog"
          aria-label="Wise, your assistant"
          className="wf-slide-in fixed bottom-24 right-4 z-40 flex h-[min(620px,calc(100vh-7.5rem))] w-[min(400px,calc(100vw-2rem))] flex-col overflow-hidden rounded-2xl border-2 border-ink bg-white shadow-hard md:right-6"
        >
          <header className="flex items-center gap-3 border-b-2 border-ink bg-brand-600 px-4 py-3 text-white">
            <span className="flex h-12 w-12 flex-none items-center justify-center overflow-hidden rounded-full bg-white">
              <WiseBot state={mood} className="h-11 w-11" />
            </span>
            <div className="min-w-0 flex-1">
              <h2 className="text-lg font-bold leading-tight">Wise</h2>
              <p className="text-[13px] text-brand-100">Answers from your scans and documents</p>
            </div>
            {messages.length > 0 && (
              <button type="button" onClick={() => { setMessages([]); setError(""); }} className="rounded-lg px-2.5 py-1.5 text-[13px] font-semibold text-brand-100 hover:bg-brand-700 hover:text-white">
                Clear
              </button>
            )}
            <button type="button" onClick={() => setOpen(false)} aria-label="Close Wise" className="flex h-9 w-9 items-center justify-center rounded-lg hover:bg-brand-700">
              <X className="h-5 w-5" aria-hidden="true" />
            </button>
          </header>

          <div className="flex-1 overflow-y-auto px-4 py-4" aria-live="polite">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center gap-3 text-center">
                <WiseBot state="listening" className="h-28 w-28" />
                <p className="font-semibold">Ask about your scans, or pick a question to start.</p>
                <ul className="flex w-full flex-col gap-2">
                  {prompts.map((p, i) => (
                    <li key={p.id} className="wf-fade-up" style={{ animationDelay: `${i * 50}ms` }}>
                      <button type="button" onClick={() => ask(p.text)} className="w-full rounded-[10px] border border-gray-300 bg-white px-3.5 py-2.5 text-left text-[15px] font-medium hover:border-brand-600 hover:bg-brand-50">
                        {p.label}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <ol className="flex flex-col gap-3">
                {messages.map((m, i) => (
                  <li key={i} className={`wf-fade-up flex flex-col gap-2 ${m.role === "user" ? "items-end" : "items-start"}`}>
                    <p className={`max-w-[88%] whitespace-pre-wrap rounded-2xl px-3.5 py-2.5 text-[15px] ${m.role === "user" ? "rounded-br-md bg-ink text-white" : "rounded-bl-md bg-soft"}`}>
                      {m.content}
                    </p>
                    {m.actions?.map((a) => (
                      <Link key={a.path} to={a.path} onClick={() => setOpen(false)} className="flex items-center gap-1.5 rounded-[10px] bg-brand-600 px-3.5 py-2 text-sm font-bold text-white hover:bg-brand-700">
                        {a.label}
                        <ArrowRight className="h-4 w-4" aria-hidden="true" />
                      </Link>
                    ))}
                    {m.sources && m.sources.length > 0 && (
                      <ul aria-label="Where this came from" className="flex max-w-[88%] flex-wrap gap-1.5">
                        {m.sources.map((s, j) => (
                          <li key={j}>
                            <Link to={s.link} onClick={() => setOpen(false)} className="block max-w-[240px] truncate rounded-full border border-gray-300 bg-white px-2.5 py-1 text-[12.5px] font-medium text-brand-700 hover:border-brand-600">
                              {s.title}
                            </Link>
                          </li>
                        ))}
                      </ul>
                    )}
                  </li>
                ))}
                {busy && (
                  <li role="status" aria-label="Wise is looking through your scans" className="flex items-center gap-2.5 self-start rounded-2xl rounded-bl-md bg-soft px-3.5 py-3">
                    <Dots />
                  </li>
                )}
              </ol>
            )}
            {error && <p role="alert" className={`${errorBox} mt-3 text-sm`}>{error}</p>}
            <div ref={end} />
          </div>

          <form onSubmit={(e) => { e.preventDefault(); ask(draft); }} className="flex items-end gap-2 border-t border-line p-3">
            <label className="sr-only" htmlFor="wise-question">Your question for Wise</label>
            <textarea
              id="wise-question"
              ref={input}
              rows={1}
              value={draft}
              maxLength={2000}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(draft); } }}
              placeholder="Ask about a finding, a scan or a requirement"
              className="max-h-28 min-h-[46px] flex-1 resize-none rounded-[10px] border border-gray-400 px-3 py-2.5 text-[15px]"
            />
            <button type="submit" disabled={busy || !draft.trim()} aria-label="Send" className="flex h-[46px] w-[46px] flex-none items-center justify-center rounded-[10px] bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50">
              <Send className="h-5 w-5" aria-hidden="true" />
            </button>
          </form>
        </section>
      )}

      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-label={open ? "Close Wise" : "Ask Wise, your assistant"}
        className="group fixed bottom-5 right-4 z-40 flex h-16 w-16 items-center justify-center rounded-full border-2 border-ink bg-white shadow-hard md:right-6"
      >
        {!open && <span aria-hidden="true" className="wf-ring absolute inset-0 rounded-full border-2 border-brand-600" />}
        <span className="flex h-full w-full items-center justify-center overflow-hidden rounded-full">
          <WiseBot state={busy ? "working" : "idle"} className="h-14 w-14" />
        </span>
      </button>
    </>
  );
}

/** Settings: the documents Wise answers from. Everyone sees the list; owners and admins change it. */
export function WiseDocuments({ canEdit }: { canEdit: boolean }) {
  const [docs, setDocs] = useState<WiseDocument[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = () => getWiseDocuments().then((r) => setDocs(r.data)).catch(() => setError("The documents could not be loaded."));
  useEffect(() => { load(); }, []);

  const run = async (work: () => Promise<unknown>, done: string, failed: string) => {
    setError("");
    setNotice("");
    setBusy(true);
    try {
      await work();
      await load();
      setNotice(done);
    } catch (e) {
      setError(apiError(e, failed));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section id="wise" className="rounded-2xl border border-gray-300 bg-white p-6">
      <div className="flex flex-wrap items-start justify-between gap-5">
        <div className="min-w-0 flex-1">
          <h2 className="text-lg font-bold">Documents for Wise</h2>
          <p className="mb-4 max-w-[62ch] text-body">
            Add requirements, user stories or release notes as text files. Wise then answers from them as well as from your scans. Up to 50 files of 1 MB each.
          </p>
        </div>
        <WiseBot state="reading" className="hidden h-20 w-20 sm:block" />
      </div>
      {error && <p role="alert" className={`${errorBox} mb-4`}>{error}</p>}
      {notice && <p role="status" className="mb-4 rounded-[10px] border border-emerald-200 bg-emerald-50 px-4 py-3 text-emerald-900">{notice}</p>}
      {docs && docs.length > 0 && (
        <ul className="mb-4 divide-y divide-line rounded-xl border border-gray-300">
          {docs.map((d) => (
            <li key={d.id} className="flex items-center gap-3 px-4 py-2.5">
              <FileText className="h-5 w-5 flex-none text-brand-600" aria-hidden="true" />
              <span className="min-w-0 flex-1 truncate font-semibold">{d.name}</span>
              <span className="text-sm text-body">{Math.max(1, Math.round(d.size / 1000))} KB</span>
              {canEdit && (
                <button type="button" disabled={busy} aria-label={`Remove ${d.name}`} onClick={() => run(() => removeWiseDocument(d.id), `${d.name} removed.`, "The document could not be removed.")}
                  className="flex h-10 w-10 items-center justify-center rounded-lg border border-gray-300 hover:bg-soft disabled:opacity-50">
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {docs && docs.length === 0 && <p className="mb-4 text-body">No documents yet. Wise answers from your scans only.</p>}
      {canEdit ? (
        <label className={`inline-flex h-12 cursor-pointer items-center rounded-[10px] bg-ink px-5 font-bold text-white ${busy ? "opacity-50" : ""}`}>
          {busy ? "Working" : "Add a document"}
          <input type="file" accept=".txt,.md,.csv,.json,.feature" className="sr-only" disabled={busy}
            onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) run(() => addWiseDocument(f), `${f.name} added. Wise can answer from it now.`, "The document could not be added."); }} />
        </label>
      ) : (
        <p className="text-body">An owner or admin of your organisation can add documents.</p>
      )}
    </section>
  );
}
