import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus } from "lucide-react";
import { Layout } from "../components/Layout";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { StatusPill } from "../components/StatusPill";
import { listAudits } from "../api/audits";
import type { AuditJob } from "../api/audits";

const sourceName = { web: "Web app", android: "Android build", ios: "iOS build" } as const;
const outputName = { security: "Security", manual: "Test cases", playwright: "Playwright", appium: "Appium" } as const;

/** Every scan the user has created, newest first. */
export function ScansListPage() {
  const [jobs, setJobs] = useState<AuditJob[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    listAudits()
      .then((r) => setJobs(r.data))
      .catch(() => setFailed(true));
  }, []);

  return (
    <Layout>
      <div className="mb-7 flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-4xl font-extrabold tracking-tight">Scans</h1>
        <Link to="/scans/new" className="flex h-[52px] items-center gap-2 rounded-[10px] bg-brand-600 px-5 font-bold text-white hover:bg-brand-700">
          <Plus className="h-[18px] w-[18px]" strokeWidth={2.4} aria-hidden="true" /> New scan
        </Link>
      </div>

      {failed ? (
        <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-red-800">
          Your scans could not be loaded. Check that the API is running, then reload the page.
        </p>
      ) : !jobs ? (
        <LoadingSpinner />
      ) : jobs.length === 0 ? (
        <section className="rounded-2xl border border-gray-300 bg-white px-6 py-12 text-center">
          <h2 className="text-xl font-bold">No scans yet</h2>
          <p className="mx-auto mt-2 max-w-md text-body">Paste a web address or upload a mobile build to run your first scan.</p>
          <Link to="/scans/new" className="mt-5 inline-flex h-12 items-center rounded-[10px] bg-ink px-5 font-bold text-white">
            Start your first scan
          </Link>
        </section>
      ) : (
        <section className="overflow-hidden rounded-2xl border border-gray-300 bg-white">
          <div className="relative overflow-x-auto">
            <table className="w-full min-w-[720px] border-collapse text-left">
              <thead>
                <tr className="bg-soft text-[13.5px] text-body">
                  <th scope="col" className="px-5 py-2.5 font-semibold">App</th>
                  <th scope="col" className="px-3 py-2.5 font-semibold">Outputs</th>
                  <th scope="col" className="px-3 py-2.5 font-semibold">Status</th>
                  <th scope="col" className="px-3 py-2.5 font-semibold">Findings</th>
                  <th scope="col" className="px-5 py-2.5 font-semibold">Created</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((j) => {
                  const draft = !j.started_at;
                  const done = j.status === "completed" || j.status === "partial";
                  return (
                    <tr key={j.id} className="border-t border-line">
                      <td className="px-5 py-3.5">
                        <Link to={draft ? `/audits/${j.id}/setup` : `/audits/${j.id}`} className="break-all font-mono text-sm font-medium text-brand-600 hover:text-brand-700">
                          {j.target_url ?? j.label}
                        </Link>
                        <div className="text-[13.5px] text-body">{[sourceName[j.source_type], j.app_name].filter(Boolean).join(", ")}</div>
                      </td>
                      <td className="px-3 py-3.5 text-sm text-body">
                        {draft ? "Not chosen yet" : (j.outputs ?? j.allowed_outputs).map((o) => outputName[o]).join(", ")}
                      </td>
                      <td className="px-3 py-3.5">
                        <StatusPill status={draft ? "draft" : j.status} progress={j.progress} />
                      </td>
                      <td className="px-3 py-3.5 whitespace-nowrap font-semibold">
                        {done ? `${j.critical_count} critical, ${j.high_count} high` : ""}
                      </td>
                      <td className="px-5 py-3.5 whitespace-nowrap text-body">{new Date(j.created_at).toLocaleString()}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </Layout>
  );
}
