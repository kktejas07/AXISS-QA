import { useEffect, useState } from "react";
import { Copy } from "lucide-react";
import { disconnect, getConnections, saveChat, saveGitHub, saveLinear } from "../api/insights";
import type { ConnectionKind, Connections } from "../api/insights";
import { apiError } from "../utils/errors";
import { errorBox, field, hint, label } from "./ui";

const section = "overflow-hidden rounded-2xl border border-gray-300 bg-white p-6";
const smallButton = "h-11 rounded-[10px] border-[1.5px] border-gray-400 bg-white px-3.5 text-sm font-semibold disabled:opacity-50";
const darkButton = "h-12 rounded-[10px] bg-ink px-5 font-bold text-white disabled:opacity-50";

const names: Record<ConnectionKind, string> = { slack: "Slack", teams: "Microsoft Teams", github: "GitHub", linear: "Linear" };
const about: Record<ConnectionKind, string> = {
  slack: "Post scan results to a Slack channel.",
  teams: "Post scan results to a Teams channel.",
  github: "Scan every pull request and report on it, and turn findings into GitHub issues.",
  linear: "Turn a finding into a Linear issue from any scan's Security tab.",
};

function CopyRow({ name, value }: { name: string; value: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => navigator.clipboard.writeText(value).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000); }).catch(() => {});
  return (
    <div>
      <dt className="text-[13.5px] font-semibold text-body">{name}</dt>
      <dd className="flex items-center gap-2">
        <code className="min-w-0 flex-1 break-all rounded-lg bg-soft px-3 py-2 font-mono text-[13px]">{value}</code>
        <button type="button" onClick={copy} aria-label={`Copy the ${name.toLowerCase()}`} className={`${smallButton} flex items-center gap-1.5`}>
          <Copy className="h-4 w-4" aria-hidden="true" />
          {copied ? "Copied" : "Copy"}
        </button>
      </dd>
    </div>
  );
}

/** Slack, Teams, GitHub and Linear. Everyone sees what is connected; owners and admins can change it. */
export function ConnectionsSection({ canEdit }: { canEdit: boolean }) {
  const [all, setAll] = useState<Connections | null>(null);
  const [editing, setEditing] = useState<ConnectionKind | null>(null);
  const [form, setForm] = useState({ webhook_url: "", events: "automatic", token: "", repo: "", fail_on: "high", api_key: "", team_key: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    getConnections().then((r) => setAll(r.data)).catch(() => setError("Your connections could not be loaded."));
  }, []);

  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setForm({ ...form, [key]: e.target.value });

  const run = async (work: () => Promise<void>, failed: string) => {
    setError("");
    setNotice("");
    setBusy(true);
    try {
      await work();
    } catch (e) {
      setError(apiError(e, failed));
    } finally {
      setBusy(false);
    }
  };

  const save = (kind: ConnectionKind) => (e: React.FormEvent) => {
    e.preventDefault();
    run(async () => {
      const { data } =
        kind === "github" ? await saveGitHub({ token: form.token.trim(), repo: form.repo.trim() || undefined, fail_on: form.fail_on })
        : kind === "linear" ? await saveLinear({ api_key: form.api_key.trim(), team_key: form.team_key.trim() })
        : await saveChat(kind, { webhook_url: form.webhook_url.trim(), events: form.events as "automatic" | "all" });
      setAll((a) => a && { ...a, [kind]: data });
      setEditing(null);
      setForm({ ...form, webhook_url: "", token: "", api_key: "" });
      setNotice(`${names[kind]} is connected.`);
    }, `Could not connect ${names[kind]}.`);
  };

  const remove = (kind: ConnectionKind) => run(async () => {
    await disconnect(kind);
    setAll((a) => a && { ...a, [kind]: { connected: false } });
    setNotice(`${names[kind]} disconnected.`);
  }, `Could not disconnect ${names[kind]}.`);

  const details = (kind: ConnectionKind): [string, string][] => {
    if (!all) return [];
    if (kind === "github") {
      const g = all.github;
      return [["Account", g.login ?? ""], ["Issues go to", g.repo ?? "Not set"], ["A pull request fails on", g.fail_on === "never" ? "Nothing: results are reported only" : `New findings at ${g.fail_on} severity or above`]];
    }
    if (kind === "linear") return [["Team", `${all.linear.team_name} (${all.linear.team_key})`]];
    return [["Posts", all[kind].events === "all" ? "Every finished scan" : "Scheduled and pull-request scans"]];
  };

  return (
    <section className={section}>
      <h2 className="text-lg font-bold">Connections</h2>
      <p className="mb-4 text-body">Send results where your team already works. Tokens and webhook addresses are stored encrypted and never shown again.</p>
      {error && <p role="alert" className={`${errorBox} mb-4`}>{error}</p>}
      {notice && <p role="status" className="mb-4 rounded-[10px] border border-emerald-200 bg-emerald-50 px-4 py-3 text-emerald-900">{notice}</p>}
      {all && (
        <ul className="divide-y divide-line">
          {(Object.keys(names) as ConnectionKind[]).map((kind) => {
            const c = all[kind];
            return (
              <li key={kind} className="flex flex-col gap-3 py-4 first:pt-0 last:pb-0">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h3 className="flex items-center gap-2.5 font-bold">
                      {names[kind]}
                      <span className={`rounded-full px-2.5 py-0.5 text-[13px] font-semibold ${c.connected ? "bg-emerald-100 text-emerald-900" : "bg-gray-100 text-body"}`}>{c.connected ? "Connected" : "Not connected"}</span>
                    </h3>
                    <p className="text-[15px] text-body">{about[kind]}</p>
                  </div>
                  {canEdit && editing !== kind && (
                    <div className="flex gap-2.5">
                      <button type="button" className={smallButton} onClick={() => { setEditing(kind); setError(""); }}>{c.connected ? "Change" : "Connect"}</button>
                      {c.connected && <button type="button" disabled={busy} className={smallButton} onClick={() => remove(kind)}>Disconnect</button>}
                    </div>
                  )}
                </div>
                {c.connected && editing !== kind && (
                  <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
                    {details(kind).map(([k, v]) => (
                      <div key={k}>
                        <dt className="text-[13.5px] font-semibold text-body">{k}</dt>
                        <dd className="break-all font-semibold">{v}</dd>
                      </div>
                    ))}
                    {kind === "github" && all.github.webhook_secret && (
                      <div className="flex flex-col gap-3 sm:col-span-2">
                        <p className="text-[15px] text-body">
                          To scan pull requests, add a webhook in the repository's settings on GitHub with the address and secret below, content type <span className="font-mono">application/json</span>, for the “Pull requests” event.
                        </p>
                        <CopyRow name="Webhook address" value={all.github.webhook_url ?? ""} />
                        <CopyRow name="Webhook secret" value={all.github.webhook_secret} />
                      </div>
                    )}
                  </dl>
                )}
                {editing === kind && (
                  <form onSubmit={save(kind)} className="flex flex-col gap-4 rounded-xl bg-soft p-4">
                    {(kind === "slack" || kind === "teams") && (
                      <div className="grid gap-4 sm:grid-cols-[1fr_260px]">
                        <label className={label}>
                          Incoming webhook address
                          <input type="url" required value={form.webhook_url} onChange={set("webhook_url")} autoComplete="off" className={`${field} font-mono`}
                            placeholder={kind === "slack" ? "https://hooks.slack.com/services/…" : "https://….webhook.office.com/…"} />
                          <span className={hint}>{kind === "slack" ? "Create an incoming webhook for the channel in Slack and paste its address." : "Add an incoming webhook (or a Workflows webhook) to the channel in Teams and paste its address."} A test message is sent when you connect.</span>
                        </label>
                        <label className={label}>
                          Post about
                          <select value={form.events} onChange={set("events")} className={field}>
                            <option value="automatic">Scheduled and pull-request scans</option>
                            <option value="all">Every finished scan</option>
                          </select>
                        </label>
                      </div>
                    )}
                    {kind === "github" && (
                      <div className="grid gap-4 sm:grid-cols-2">
                        <label className={`${label} sm:col-span-2`}>
                          Personal access token
                          <input type="password" required minLength={10} value={form.token} onChange={set("token")} autoComplete="off" className={`${field} font-mono`} />
                          <span className={hint}>A fine-grained token for your repositories with read access to Contents and read and write access to Issues, Pull requests and Commit statuses.</span>
                        </label>
                        <label className={label}>
                          Repository for issues (optional)
                          <input value={form.repo} onChange={set("repo")} placeholder="acme/shop" className={`${field} font-mono`} />
                        </label>
                        <label className={label}>
                          A pull request fails when it adds
                          <select value={form.fail_on} onChange={set("fail_on")} className={field}>
                            <option value="high">A high or critical finding</option>
                            <option value="critical">A critical finding</option>
                            <option value="never">Never: report only</option>
                          </select>
                        </label>
                      </div>
                    )}
                    {kind === "linear" && (
                      <div className="grid gap-4 sm:grid-cols-[1fr_160px]">
                        <label className={label}>
                          API key
                          <input type="password" required minLength={10} value={form.api_key} onChange={set("api_key")} autoComplete="off" className={`${field} font-mono`} />
                          <span className={hint}>Create a personal API key in Linear under Settings, Security and access.</span>
                        </label>
                        <label className={label}>
                          Team key
                          <input required value={form.team_key} onChange={set("team_key")} placeholder="ENG" maxLength={10} className={`${field} font-mono uppercase`} />
                        </label>
                      </div>
                    )}
                    <div className="flex flex-wrap gap-2.5">
                      <button type="submit" disabled={busy} className={darkButton}>{busy ? `Checking with ${names[kind]}` : `Connect ${names[kind]}`}</button>
                      <button type="button" onClick={() => setEditing(null)} className="h-12 rounded-[10px] border-[1.5px] border-ink bg-white px-5 font-semibold">Cancel</button>
                    </div>
                  </form>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {!canEdit && <p className="mt-4 text-body">An owner or admin of your organisation can change these.</p>}
    </section>
  );
}
