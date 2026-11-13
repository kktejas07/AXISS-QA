import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, Download } from "lucide-react";
import { getLibrary, packCsvPath } from "../api/wise";
import type { ScanPreset, TestPack } from "../api/wise";
import { BookShelf, ClipboardTicks, Rocket } from "../components/Illustrations";
import { Layout } from "../components/Layout";
import { Skeleton } from "../components/LoadingSpinner";
import { card, errorBox, pageTitle } from "../components/ui";
import { useCan } from "../hooks/useMe";
import { downloadFromApi } from "../utils/download";

const outputName: Record<string, string> = { security: "Security audit", manual: "Manual test cases", playwright: "Playwright scripts", appium: "Appium scripts" };

/** Ready-made starting points: scan presets and packs of test cases. */
export function LibraryPage() {
  const canScan = useCan("scan.run");
  const [data, setData] = useState<{ scan_presets: ScanPreset[]; test_packs: TestPack[] } | null>(null);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    getLibrary().then((r) => setData(r.data)).catch(() => setFailed(true));
  }, []);

  return (
    <Layout>
      <div className="mb-8 flex flex-wrap items-center justify-between gap-6">
        <div>
          <h1 className={pageTitle}>Library</h1>
          <p className="mt-1 max-w-[60ch] text-body">Ready-made starting points, so no scan or test plan begins from a blank page.</p>
        </div>
        <BookShelf className="hidden h-28 w-auto sm:block" />
      </div>
      {failed && <p role="alert" className={errorBox}>The library could not be loaded. Reload the page to try again.</p>}
      {!data && !failed && <Skeleton rows={5} className="max-w-xl" />}
      {data && (
        <div className="flex flex-col gap-10">
          <section aria-labelledby="presets">
            <div className="mb-4 flex items-center gap-4">
              <Rocket className="h-16 w-auto" />
              <div>
                <h2 id="presets" className="text-2xl font-bold">Scan presets</h2>
                <p className="text-body">Pick one on step 2 of a new scan and the outputs and depth are filled in for you.</p>
              </div>
            </div>
            <ul className="grid gap-4 sm:grid-cols-2">
              {data.scan_presets.map((p, i) => (
                <li key={p.id} className={`${card} wf-fade-up wf-lift flex flex-col gap-3 p-5`} style={{ animationDelay: `${i * 60}ms` }}>
                  <h3 className="text-lg font-bold">{p.name}</h3>
                  <p className="flex-1 text-body">{p.about}</p>
                  <ul className="flex flex-wrap gap-1.5">
                    {p.outputs.map((o) => <li key={o} className="rounded-full bg-brand-50 px-2.5 py-0.5 text-[13px] font-semibold text-brand-700">{outputName[o]}</li>)}
                    <li className="rounded-full bg-gray-100 px-2.5 py-0.5 text-[13px] font-semibold text-body">{p.depth[0].toUpperCase() + p.depth.slice(1)} depth</li>
                  </ul>
                  {canScan && <Link to={`/scans/new?preset=${p.id}`} className="self-start font-semibold text-brand-600 hover:text-brand-700">Start a scan with this preset</Link>}
                </li>
              ))}
            </ul>
          </section>

          <section aria-labelledby="packs">
            <div className="mb-4 flex items-center gap-4">
              <ClipboardTicks className="h-16 w-auto" />
              <div>
                <h2 id="packs" className="text-2xl font-bold">Test-case packs</h2>
                <p className="text-body">Test cases written for the parts almost every app has. Read them here or download a pack as a spreadsheet.</p>
              </div>
            </div>
            <ul className="flex flex-col gap-3">
              {data.test_packs.map((pack) => (
                <li key={pack.id} className={`${card} overflow-hidden`}>
                  <div className="flex flex-wrap items-center gap-3 p-4">
                    <button type="button" aria-expanded={open === pack.id} onClick={() => setOpen(open === pack.id ? null : pack.id)} className="flex min-h-[44px] min-w-0 flex-1 items-center gap-3 text-left">
                      <ChevronDown className={`h-5 w-5 flex-none transition-transform motion-reduce:transition-none ${open === pack.id ? "rotate-180" : ""}`} aria-hidden="true" />
                      <span className="min-w-0">
                        <span className="block text-lg font-bold">{pack.name}</span>
                        <span className="block text-body">{pack.about} {pack.cases.length} test cases.</span>
                      </span>
                    </button>
                    <button type="button" onClick={() => downloadFromApi(packCsvPath(pack.id), `wiseflow-${pack.id}.csv`)} aria-label={`Download the ${pack.name} pack`}
                      className="flex h-11 items-center gap-2 rounded-[10px] border-[1.5px] border-ink bg-white px-4 text-sm font-semibold">
                      <Download className="h-4 w-4" aria-hidden="true" />
                      Download
                    </button>
                  </div>
                  {open === pack.id && (
                    <ol className="wf-fade-up divide-y divide-line border-t border-line bg-soft">
                      {pack.cases.map((c) => (
                        <li key={c.id} className="flex flex-col gap-1.5 px-5 py-3.5">
                          <span className="flex flex-wrap items-center gap-2.5">
                            <span className="font-mono text-[13px] font-bold text-brand-700">{c.id}</span>
                            <span className="font-semibold">{c.title}</span>
                            <span className="rounded-full bg-white px-2 py-0.5 text-[12.5px] font-semibold text-body">{c.category}, {c.priority.toLowerCase()} priority</span>
                          </span>
                          <ol className="list-decimal pl-5 text-[15px]">{c.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
                          <span className="text-[15px]"><span className="font-semibold">Expected:</span> {c.expected_result}</span>
                        </li>
                      ))}
                    </ol>
                  )}
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </Layout>
  );
}
