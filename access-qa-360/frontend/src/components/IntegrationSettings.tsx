import { useEffect, useState } from "react";
import { Copy } from "lucide-react";
import { createApiKey, disconnectJira, getApiKeys, getJira, revokeApiKey, saveJira } from "../api/integrations";
import type { ApiKey, JiraConnection } from "../api/integrations";
import { apiError } from "../utils/errors";
import { errorBox, field, hint, label } from "./ui";

const section = "overflow-hidden rounded-2xl border border-gray-300 bg-white";
const smallButton = "h-11 rounded-[10px] border-[1.5px] border-gray-400 bg-white px-3.5 text-sm font-semibold disabled:opacity-50";
const darkButton = "h-12 rounded-[10px] bg-ink px-5 font-bold text-white disabled:opacity-50";
const apiBase = () => new URL(import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1", window.location.origin).toString().replace(/\/$/, "");

/** API keys for build pipelines. Only owners and admins see this. */
export function ApiKeysSection() {
  const [keys, setKeys] = useState<ApiKey[] | null>(null);
  const [name, setName] = useState("");
  const [fresh, setFresh] = useState<ApiKey | null>(null);
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = () => getApiKeys().then((r) => setKeys(r.data));
  useEffect(() => {
    load().catch(() => setError("The API keys could not be loaded."));
  }, []);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      setFresh((await createApiKey(name.trim())).data);
      setCopied(false);
      setName("");
      await load();
    } catch (err) {
      setError(apiError(err, "Could not create the key."));
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (key: ApiKey) => {
    setError("");
    setBusy(true);
    try {
      await revokeApiKey(key.id);
      if (fresh?.id === key.id) setFresh(null);
      await load();
    } catch (err) {
      setError(apiError(err, "Could not revoke the key."));
    } finally {
      setBusy(false);
    }
  };

  const copy = async () => {
    if (!fresh?.key) return;
    try {
      await navigator.clipboard.writeText(fresh.key);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  const example = `curl -X POST ${apiBase()}/audits \\
  -H "Authorization: Bearer $WISEFLOW_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"target_url": "https://staging.your-app.com"}'

# then read the result until status is completed, partial or failed
curl ${apiBase()}/audits/SCAN_ID -H "Authorization: Bearer $WISEFLOW_API_KEY"`;

  return (
    <section className={section}>
      <div className="px-5 py-4">
        <h2 className="text-lg font-bold">API keys</h2>
        <p className="text-body">For build pipelines. A key can start scans and read results, and nothing else. Scans it starts are recorded under the person who created it.</p>
      </div>

      {error && <p role="alert" className={`${errorBox} mx-5 mb-4`}>{error}</p>}

      {fresh?.key && (
        <div role="status" className="mx-5 mb-4 flex flex-col gap-3 rounded-[12px] border-2 border-ink bg-white p-4">
          <p className="font-bold">Copy this key now. It is not shown again.</p>
          <code className="break-all rounded-[10px] bg-soft px-3.5 py-3 font-mono text-[13.5px]">{fresh.key}</code>
          <div className="flex flex-wrap gap-2.5">
            <button type="button" onClick={copy} className="flex h-11 items-center gap-2 rounded-[10px] bg-ink px-4 text-sm font-bold text-white">
              <Copy className="h-4 w-4" aria-hidden="true" />
              {copied ? "Copied" : "Copy key"}
            </button>
            <button type="button" onClick={() => setFresh(null)} className={smallButton}>Done</button>
          </div>
        </div>
      )}

      {keys && keys.length > 0 && (
        <div className="relative overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse text-left">
            <thead>
              <tr className="bg-soft text-[13.5px] text-body">
                <th scope="col" className="px-5 py-2.5 font-semibold">Name</th>
                <th scope="col" className="px-3 py-2.5 font-semibold">Key</th>
                <th scope="col" className="px-3 py-2.5 font-semibold">Created by</th>
                <th scope="col" className="px-3 py-2.5 font-semibold">Last used</th>
                <th scope="col" className="px-5 py-2.5 font-semibold"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => (
                <tr key={k.id} className="border-t border-line">
                  <td className="px-5 py-3 font-semibold">{k.name}</td>
                  <td className="px-3 py-3 font-mono text-[13px]">{k.prefix}…</td>
                  <td className="break-all px-3 py-3 text-body">{k.created_by_email}</td>
                  <td className="whitespace-nowrap px-3 py-3 text-body">{k.last_used_at ? new Date(k.last_used_at).toLocaleString() : "Never"}</td>
                  <td className="px-5 py-2 text-right">
                    <button type="button" disabled={busy} onClick={() => revoke(k)} aria-label={`Revoke the key ${k.name}`} className={smallButton}>Revoke</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <form onSubmit={create} className="flex flex-wrap items-end gap-3 border-t border-line p-5">
        <label className={`${label} min-w-0 flex-[1_1_260px]`}>
          Name for a new key
          <input required maxLength={120} value={name} onChange={(e) => setName(e.target.value)} placeholder="GitHub Actions" className={field} />
        </label>
        <button type="submit" disabled={busy} className={darkButton}>Create key</button>
      </form>

      <details className="border-t border-line">
        <summary className="flex min-h-[52px] cursor-pointer items-center px-5 font-semibold">How to start a scan from a pipeline</summary>
        <div className="flex flex-col gap-3 px-5 pb-5">
          <p className="text-body">Store the key as a secret named WISEFLOW_API_KEY, then call the API. The answer includes the scan's id; critical_count and high_count tell the pipeline whether to fail the build.</p>
          <pre className="overflow-x-auto rounded-[10px] bg-ink px-4 py-3.5 font-mono text-[13px] leading-relaxed text-gray-100">{example}</pre>
        </div>
      </details>
    </section>
  );
}

/** Connect Jira Cloud so findings can be turned into issues. */
export function JiraSection({ canEdit }: { canEdit: boolean }) {
  const [jira, setJira] = useState<JiraConnection | null>(null);
  const [form, setForm] = useState({ base_url: "", email: "", api_token: "", project_key: "", issue_type: "Bug" });
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    getJira().then((r) => setJira(r.data)).catch(() => setError("The Jira connection could not be loaded."));
  }, []);

  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [key]: e.target.value });

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setNotice("");
    setBusy(true);
    try {
      const { data } = await saveJira({ ...form, base_url: form.base_url.trim(), email: form.email.trim(), project_key: form.project_key.trim() });
      setJira(data);
      setEditing(false);
      setForm({ ...form, api_token: "" });
      setNotice(`Connected to ${data.project_name} (${data.project_key}).`);
    } catch (err) {
      setError(apiError(err, "Could not connect to Jira."));
    } finally {
      setBusy(false);
    }
  };

  const disconnect = async () => {
    setError("");
    setNotice("");
    setBusy(true);
    try {
      await disconnectJira();
      setJira({ connected: false, base_url: null, email: null, project_key: null, project_name: null, issue_type: null });
      setNotice("Jira disconnected. Issues already created stay in Jira.");
    } catch (err) {
      setError(apiError(err, "Could not disconnect Jira."));
    } finally {
      setBusy(false);
    }
  };

  const startEditing = () => {
    setForm({ base_url: jira?.base_url ?? "", email: jira?.email ?? "", api_token: "", project_key: jira?.project_key ?? "", issue_type: jira?.issue_type ?? "Bug" });
    setEditing(true);
  };

  return (
    <section className={`${section} p-6`}>
      <h2 className="text-lg font-bold">Jira</h2>
      <p className="mb-4 text-body">Turn a finding into a Jira issue from any scan's Security tab. Works with Jira Cloud.</p>
      {error && <p role="alert" className={`${errorBox} mb-4`}>{error}</p>}
      {notice && <p role="status" className="mb-4 rounded-[10px] border border-emerald-200 bg-emerald-50 px-4 py-3 text-emerald-900">{notice}</p>}

      {!jira ? null : jira.connected && !editing ? (
        <div className="flex flex-col gap-4">
          <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
            {[
              ["Site", jira.base_url],
              ["Project", `${jira.project_name} (${jira.project_key})`],
              ["Issues are created as", jira.issue_type],
              ["Signed in as", jira.email],
            ].map(([k, v]) => (
              <div key={k}>
                <dt className="text-[13.5px] font-semibold text-body">{k}</dt>
                <dd className="break-all font-semibold">{v}</dd>
              </div>
            ))}
          </dl>
          {canEdit && (
            <div className="flex flex-wrap gap-2.5">
              <button type="button" onClick={startEditing} className={smallButton}>Change</button>
              <button type="button" disabled={busy} onClick={disconnect} className={smallButton}>Disconnect</button>
            </div>
          )}
        </div>
      ) : !canEdit ? (
        <p className="text-body">Jira is not connected. An owner or admin of your organisation can connect it.</p>
      ) : (
        <form onSubmit={save} className="flex flex-col gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className={label}>
              Jira address
              <input type="url" required value={form.base_url} onChange={set("base_url")} placeholder="https://your-team.atlassian.net" className={`${field} font-mono`} />
            </label>
            <label className={label}>
              Jira account email
              <input type="email" required value={form.email} onChange={set("email")} autoComplete="off" className={field} />
            </label>
            <label className={label}>
              API token
              <input type="password" required minLength={8} value={form.api_token} onChange={set("api_token")} autoComplete="off" className={field} />
              <span className={hint}>Create one in your Atlassian account under Security, API tokens. It is stored encrypted and never shown again.</span>
            </label>
            <div className="grid grid-cols-2 gap-4">
              <label className={label}>
                Project key
                <input required value={form.project_key} onChange={set("project_key")} placeholder="SEC" maxLength={20} className={`${field} font-mono uppercase`} />
              </label>
              <label className={label}>
                Issue type
                <input required value={form.issue_type} onChange={set("issue_type")} maxLength={60} className={field} />
              </label>
            </div>
          </div>
          <div className="flex flex-wrap gap-2.5">
            <button type="submit" disabled={busy} className={darkButton}>{busy ? "Checking with Jira" : "Connect Jira"}</button>
            {editing && <button type="button" onClick={() => setEditing(false)} className="h-12 rounded-[10px] border-[1.5px] border-ink bg-white px-5 font-semibold">Cancel</button>}
          </div>
        </form>
      )}
    </section>
  );
}
