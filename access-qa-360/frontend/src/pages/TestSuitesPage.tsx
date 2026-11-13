import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Plus } from "lucide-react";
import { Layout } from "../components/Layout";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { getSuites } from "../api/suites";
import type { Suite } from "../types";
import { backLink, card, emptyState, errorBox, pageTitle, primaryButton } from "../components/ui";

const statusLook: Record<Suite["status"], { text: string; look: string }> = {
  active: { text: "Ready", look: "bg-emerald-100 text-emerald-800" },
  draft: { text: "Being written", look: "bg-yellow-100 text-yellow-900" },
  archived: { text: "Archived", look: "bg-gray-100 text-gray-800" },
};

export function TestSuitesPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [suites, setSuites] = useState<Suite[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    let alive = true;
    const load = () =>
      getSuites(projectId)
        .then((r) => alive && setSuites(r.data))
        .catch(() => alive && setFailed(true));
    load();
    // A new suite is written in the background; keep checking until none are still drafts.
    const timer = setInterval(() => suites?.some((s) => s.status === "draft") && load(), 4000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [projectId, suites?.some((s) => s.status === "draft")]);

  return (
    <Layout>
      <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link to="/projects" className={backLink}>Projects</Link>
          <h1 className={`${pageTitle} mt-1`}>Test suites</h1>
        </div>
        <Link to={`/projects/${projectId}/suites/new`} className={primaryButton}>
          <Plus className="h-[18px] w-[18px]" strokeWidth={2.4} aria-hidden="true" /> Generate tests
        </Link>
      </div>
      {failed ? (
        <p role="alert" className={errorBox}>The test suites could not be loaded. Check the project still exists, then reload the page.</p>
      ) : !suites ? (
        <LoadingSpinner />
      ) : suites.length === 0 ? (
        <p className={emptyState}>No test suites yet. Describe a feature in plain words and Wiseflow writes Playwright tests for it.</p>
      ) : (
        <ul className={`${card} overflow-hidden`}>
          {suites.map((s, i) => (
            <li key={s.id} className={`flex flex-wrap items-center justify-between gap-x-6 gap-y-3 px-5 py-4 ${i ? "border-t border-line" : ""}`}>
              <div className="min-w-0 flex-[1_1_320px]">
                <p className="font-bold">{s.name}</p>
                <p className="line-clamp-2 text-[14.5px] text-body">{s.feature_description}</p>
              </div>
              <div className="flex items-center gap-4">
                <span className={`whitespace-nowrap rounded-full px-2.5 py-1 text-[13px] font-bold ${statusLook[s.status].look}`}>{statusLook[s.status].text}</span>
                {s.status === "active" && (
                  <Link to={`/projects/${projectId}/suites/${s.id}/runs`} className="whitespace-nowrap font-semibold text-brand-600 hover:text-brand-700">
                    Runs
                  </Link>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Layout>
  );
}
