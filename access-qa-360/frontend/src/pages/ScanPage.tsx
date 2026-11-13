import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Layout } from "../components/Layout";
import { createScan } from "../api/scans";
import { getProjects } from "../api/projects";
import { useCan } from "../hooks/useMe";
import type { AuthConfig, Project, ScanProfile, ScanType } from "../types";
import { apiError } from "../utils/errors";
import { backLink, card, errorBox, field, hint, label, pageTitle, primaryButton } from "../components/ui";

const scanTypes: { value: ScanType; label: string; desc: string }[] = [
  { value: "passive", label: "Passive", desc: "Only reads pages. Safe for a live site." },
  { value: "active", label: "Active", desc: "Submits forms and changes data. Use on a test site." },
  { value: "hybrid", label: "Hybrid", desc: "Reads everything, submits only low-risk forms." },
];

const profiles: { value: ScanProfile; label: string }[] = [
  { value: "owasp_top10", label: "OWASP Top 10" },
  { value: "pci_dss", label: "PCI DSS" },
  { value: "hipaa", label: "HIPAA" },
  { value: "custom", label: "Custom" },
];

const split = (text: string) => text.split(",").map((s) => s.trim()).filter(Boolean);

/** A quick OWASP check of one address. The full flow, with test cases and automation, is under New scan. */
export function ScanPage() {
  const navigate = useNavigate();
  const canScan = useCan("scan.run");
  const [url, setUrl] = useState("");
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [projectId, setProjectId] = useState("");

  useEffect(() => {
    getProjects()
      .then((r) => {
        setProjects(r.data);
        if (r.data[0]) {
          setProjectId(r.data[0].id);
          setUrl((current) => current || r.data[0].base_url);
        }
      })
      .catch(() => setProjects([]));
  }, []);
  const [scanType, setScanType] = useState<ScanType>("passive");
  const [profile, setProfile] = useState<ScanProfile>("owasp_top10");
  const [auth, setAuth] = useState<AuthConfig>({ type: "none" });
  const [includePaths, setIncludePaths] = useState("");
  const [excludePaths, setExcludePaths] = useState("");
  const [crawlDepth, setCrawlDepth] = useState(3);
  const [rateLimit, setRateLimit] = useState(10);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const { data } = await createScan({
        project_id: projectId,
        url: url.trim(),
        scan_type: scanType,
        profile,
        auth,
        include_paths: split(includePaths),
        exclude_paths: split(excludePaths),
        crawl_depth: crawlDepth,
        rate_limit: rateLimit,
      });
      // The results page shows progress while the scan runs.
      navigate(`/scans/${data.id}`);
    } catch (err) {
      setError(apiError(err, "The scan could not start. Check the address and try again."));
      setBusy(false);
    }
  };

  if (canScan === false) {
    return (
      <Layout>
        <h1 className={`${pageTitle} mb-4`}>Quick security scan</h1>
        <p className={`${card} max-w-xl px-5 py-4`}>Your role is Viewer, so you can see scans and results but not start new ones.</p>
      </Layout>
    );
  }

  if (projects && projects.length === 0) {
    return (
      <Layout>
        <Link to="/scans/new" className={backLink}>New scan</Link>
        <h1 className={`${pageTitle} mb-4 mt-1`}>Quick security scan</h1>
        <div className={`${card} flex max-w-xl flex-col items-start gap-4 p-6`}>
          <p>A quick scan is saved under a project, and you do not have one yet.</p>
          <Link to="/projects/new" className={primaryButton}>Create a project</Link>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <Link to="/scans/new" className={backLink}>New scan</Link>
      <h1 className={`${pageTitle} mt-1`}>Quick security scan</h1>
      <p className="mb-7 mt-1 max-w-2xl text-body">Checks one web address against a security profile. For test cases and automation scripts as well, use New scan.</p>

      <form onSubmit={submit} className="flex max-w-3xl flex-col gap-6">
        <div className={`${card} flex flex-col gap-5 p-7`}>
          <label className={`${label} max-w-md`}>
            Project
            <select
              required
              value={projectId}
              onChange={(e) => {
                setProjectId(e.target.value);
                const chosen = projects?.find((p) => p.id === e.target.value);
                if (chosen) setUrl(chosen.base_url);
              }}
              className={`${field} px-2.5`}
            >
              {(projects ?? []).map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </label>
          <label className={label}>
            Web address
            <input type="url" required value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://your-app.com" className={`${field} font-mono`} />
          </label>

          <fieldset>
            <legend className="mb-2 text-sm font-semibold">How far the scan may go</legend>
            <div className="grid gap-3 sm:grid-cols-3">
              {scanTypes.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  aria-pressed={scanType === t.value}
                  onClick={() => setScanType(t.value)}
                  className={`flex flex-col gap-1 rounded-[12px] border-2 p-4 text-left ${scanType === t.value ? "border-brand-600 bg-brand-50" : "border-gray-300 bg-white"}`}
                >
                  <span className="font-bold">{t.label}</span>
                  <span className="text-[13.5px] text-body">{t.desc}</span>
                </button>
              ))}
            </div>
          </fieldset>

          <label className={`${label} max-w-xs`}>
            Security profile
            <select value={profile} onChange={(e) => setProfile(e.target.value as ScanProfile)} className={`${field} px-2.5`}>
              {profiles.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </label>
        </div>

        <details className={`${card} group`}>
          <summary className="flex min-h-[56px] cursor-pointer items-center px-7 font-bold">Scope, speed and sign-in</summary>
          <div className="flex flex-col gap-5 border-t border-line p-7">
            <div className="grid gap-5 sm:grid-cols-2">
              <label className={label}>
                Only these paths
                <input value={includePaths} onChange={(e) => setIncludePaths(e.target.value)} placeholder="/app/*, /api/v2/*" className={`${field} font-mono`} />
                <span className={hint}>Separate with commas. Empty means the whole site.</span>
              </label>
              <label className={label}>
                Skip these paths
                <input value={excludePaths} onChange={(e) => setExcludePaths(e.target.value)} placeholder="/admin/*, /static/*" className={`${field} font-mono`} />
              </label>
              <label className={label}>
                Link levels to follow: {crawlDepth}
                <input type="range" min={1} max={5} value={crawlDepth} onChange={(e) => setCrawlDepth(Number(e.target.value))} className="h-12 w-full accent-brand-600" />
              </label>
              <label className={label}>
                Requests per second
                <input type="number" min={1} max={100} value={rateLimit} onChange={(e) => setRateLimit(Number(e.target.value))} className={field} />
              </label>
            </div>
            <label className={`${label} max-w-xs`}>
              Signing in to the app
              <select value={auth.type} onChange={(e) => setAuth({ type: e.target.value as AuthConfig["type"] })} className={`${field} px-2.5`}>
                <option value="none">Not needed</option>
                <option value="cookie">Session cookie</option>
                <option value="bearer">Bearer token</option>
                <option value="basic">Username and password</option>
                <option value="oauth">OAuth 2.0</option>
              </select>
            </label>
            {(auth.type === "bearer" || auth.type === "cookie" || auth.type === "oauth") && (
              <label className={label}>
                {auth.type === "cookie" ? "Cookie header" : "Token"}
                <input value={auth.value ?? ""} onChange={(e) => setAuth({ ...auth, value: e.target.value })} autoComplete="off" className={`${field} font-mono`} />
                <span className={hint}>Use a test account. The value is sent with every request of the scan.</span>
              </label>
            )}
            {auth.type === "basic" && (
              <div className="grid gap-5 sm:grid-cols-2">
                <label className={label}>
                  Username
                  <input value={auth.username ?? ""} onChange={(e) => setAuth({ ...auth, username: e.target.value })} autoComplete="off" className={field} />
                </label>
                <label className={label}>
                  Password
                  <input type="password" value={auth.password ?? ""} onChange={(e) => setAuth({ ...auth, password: e.target.value })} autoComplete="off" className={field} />
                </label>
              </div>
            )}
          </div>
        </details>

        {error && <p role="alert" className={errorBox}>{error}</p>}
        <button type="submit" disabled={busy} className={`${primaryButton} self-start`}>
          {busy ? "Starting" : "Start scan"}
          {!busy && <ArrowRight className="h-[18px] w-[18px]" strokeWidth={2.4} aria-hidden="true" />}
        </button>
      </form>
    </Layout>
  );
}
