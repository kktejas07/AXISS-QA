import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Bell, Check, Download, X } from "lucide-react";
import { getFirstSteps, getNotifications, sbomPath } from "../api/workspace";
import type { FirstSteps, Notice } from "../api/workspace";
import { downloadFromApi } from "../utils/download";
import { card } from "./ui";

const SEEN = "notices-seen";
const HIDE = "first-steps-hidden";
const read = (key: string) => {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
};
const write = (key: string, value: string) => {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* works without being remembered */
  }
};

/** A bell with what happened lately: scans that finished, scheduled runs that were skipped. */
export function NotificationBell({ dark }: { dark?: boolean }) {
  const [items, setItems] = useState<Notice[]>([]);
  const [open, setOpen] = useState(false);
  const [seen, setSeen] = useState(() => read(SEEN) ?? "");
  const box = useRef<HTMLDivElement>(null);

  const load = () => getNotifications().then((r) => { setItems(r.data); return r.data; }).catch(() => [] as Notice[]);
  useEffect(() => {
    load();
    const timer = setInterval(load, 60000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    if (!open) return;
    // Opening always asks again, so a scan that finished a moment ago is in the list.
    load().then((latest) => {
      if (latest[0]) { setSeen(latest[0].at); write(SEEN, latest[0].at); }
    });
    const away = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", away); document.removeEventListener("keydown", esc); };
  }, [open]);

  const fresh = items.filter((i) => i.at > seen).length;
  const toggle = () => {
    setOpen(!open);
    if (!open && items[0]) {
      setSeen(items[0].at);
      write(SEEN, items[0].at);
    }
  };
  return (
    <div ref={box} className="relative">
      <button type="button" onClick={toggle} aria-expanded={open} aria-label={fresh ? `Notifications, ${fresh} new` : "Notifications"}
        className={`relative flex h-11 w-11 items-center justify-center rounded-[10px] ${dark ? "text-brand-100 hover:text-white" : "text-body hover:bg-soft hover:text-ink"}`}>
        <Bell className="h-5 w-5" aria-hidden="true" />
        {fresh > 0 && <span className="wf-pop absolute right-1.5 top-1.5 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-red-600 px-1 text-[11px] font-bold text-white">{fresh}</span>}
      </button>
      {open && (
        <div role="dialog" aria-label="Notifications" className="wf-slide-in absolute right-0 top-12 z-30 w-[min(340px,calc(100vw-2rem))] overflow-hidden rounded-xl border-2 border-ink bg-white text-ink shadow-hard md:left-0 md:right-auto" style={{ transformOrigin: "top" }}>
          <h2 className="border-b border-line px-4 py-3 font-bold">Notifications</h2>
          {items.length === 0 ? (
            <p className="px-4 py-6 text-center text-body">Nothing in the last two weeks. Finished scans show up here.</p>
          ) : (
            <ul className="max-h-[360px] divide-y divide-line overflow-y-auto">
              {items.map((i) => (
                <li key={i.id}>
                  <Link to={i.path} onClick={() => setOpen(false)} className="flex gap-3 px-4 py-3 hover:bg-soft">
                    <span aria-hidden="true" className={`mt-1.5 h-2.5 w-2.5 flex-none rounded-full ${i.tone === "bad" ? "bg-red-600" : "bg-emerald-500"}`} />
                    <span className="min-w-0">
                      <span className="block break-words text-[14.5px] font-medium">{i.text}</span>
                      <span className="text-[13px] text-body">{new Date(i.at).toLocaleString()}</span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

/** First steps for a new organisation. Goes away when all are done or when dismissed. */
export function FirstStepsCard() {
  const [data, setData] = useState<FirstSteps | null>(null);
  const [hidden, setHidden] = useState(() => read(HIDE) === "1");
  useEffect(() => {
    if (!hidden) getFirstSteps().then((r) => setData(r.data)).catch(() => {});
  }, [hidden]);
  if (hidden || !data || data.done === data.total) return null;
  return (
    <section aria-label="Getting started" className={`${card} wf-fade-up mb-7 p-5`}>
      <div className="mb-3 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold">Getting started</h2>
          <p className="text-body">{data.done} of {data.total} done</p>
        </div>
        <button type="button" onClick={() => { setHidden(true); write(HIDE, "1"); }} aria-label="Hide getting started" className="flex h-10 w-10 items-center justify-center rounded-lg text-body hover:bg-soft hover:text-ink">
          <X className="h-5 w-5" aria-hidden="true" />
        </button>
      </div>
      <div className="mb-4 h-2 overflow-hidden rounded-full bg-line" role="progressbar" aria-valuenow={data.done} aria-valuemin={0} aria-valuemax={data.total} aria-label="Getting started progress">
        <div className="h-full rounded-full bg-brand-600 transition-[width] duration-500 motion-reduce:transition-none" style={{ width: `${(data.done / data.total) * 100}%` }} />
      </div>
      <ol className="grid gap-2.5 sm:grid-cols-2">
        {data.steps.map((s) => (
          <li key={s.id}>
            <Link to={s.path} className={`flex h-full items-start gap-3 rounded-xl border p-3.5 ${s.done ? "border-line bg-soft" : "border-gray-300 hover:border-brand-600"}`}>
              <span className={`mt-0.5 flex h-6 w-6 flex-none items-center justify-center rounded-full border-2 ${s.done ? "border-brand-600 bg-brand-600 text-white" : "border-gray-400"}`}>
                {s.done && <Check className="h-3.5 w-3.5" strokeWidth={3.2} aria-hidden="true" />}
              </span>
              <span>
                <span className={`block font-semibold ${s.done ? "text-body line-through" : ""}`}>{s.label}{s.done && <span className="sr-only"> (done)</span>}</span>
                <span className="text-[14px] text-body">{s.about}</span>
              </span>
            </Link>
          </li>
        ))}
      </ol>
    </section>
  );
}

/** Code scans: download the list of packages as a CycloneDX file. */
export function SbomCard({ auditId, count }: { auditId: string; count: number }) {
  return (
    <section className={`${card} flex flex-wrap items-center justify-between gap-4 p-5`}>
      <div className="min-w-0 flex-1">
        <h2 className="text-lg font-bold">Software bill of materials</h2>
        <p className="max-w-[62ch] text-body">The {count} packages with exact versions that this scan found, in CycloneDX format, for customers and auditors who ask what your product is built from.</p>
      </div>
      <button type="button" onClick={() => downloadFromApi(sbomPath(auditId), "wiseflow-sbom.cdx.json")} className="flex h-11 items-center gap-2 rounded-[10px] border-[1.5px] border-ink bg-white px-4 text-sm font-semibold">
        <Download className="h-4 w-4" aria-hidden="true" />
        Download SBOM
      </button>
    </section>
  );
}
