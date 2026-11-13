import { useEffect, useState } from "react";
import { Layout } from "../components/Layout";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { createResetLink, getAdminOverview, getAdminScans, getAdminUsers, updateAdminUser } from "../api/admin";
import { useMe } from "../hooks/useMe";
import type { AdminOverview, AdminScan, AdminUser, UserRole } from "../types";
import { StatusPill } from "../components/StatusPill";

function Stat({ label, value, note, tone }: { label: string; value: number; note: string; tone?: "bad" }) {
  return (
    <div className="flex flex-col gap-1 px-6 py-5 border-b border-line last:border-b-0 sm:border-b-0 sm:border-r sm:last:border-r-0">
      <dt className="text-sm font-semibold text-body">{label}</dt>
      <dd className={`text-[40px] leading-tight font-extrabold ${tone === "bad" ? "text-red-700" : ""}`}>{value}</dd>
      <span className="text-[13.5px] text-body">{note}</span>
    </div>
  );
}

export function AdminPage() {
  const me = useMe();
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [scans, setScans] = useState<AdminScan[]>([]);
  const [loadFailed, setLoadFailed] = useState(false);
  const [error, setError] = useState("");
  const [savingId, setSavingId] = useState<string | null>(null);
  const [resetLink, setResetLink] = useState<{ url: string; email: string; expires_at: string } | null>(null);
  const [copied, setCopied] = useState(false);

  const loadOverview = () => getAdminOverview().then((r) => setOverview(r.data));

  useEffect(() => {
    Promise.all([loadOverview(), getAdminUsers().then((r) => setUsers(r.data)), getAdminScans().then((r) => setScans(r.data))]).catch(
      () => setLoadFailed(true)
    );
  }, []);

  const change = async (user: AdminUser, changes: { role?: UserRole; is_active?: boolean }) => {
    setError("");
    setSavingId(user.id);
    try {
      const res = await updateAdminUser(user.id, changes);
      setUsers((list) => list.map((u) => (u.id === user.id ? res.data : u)));
      loadOverview().catch(() => {});
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      setError(detail ?? `Could not update ${user.email}. Try again.`);
    } finally {
      setSavingId(null);
    }
  };

  const makeResetLink = async (user: AdminUser) => {
    setError("");
    setResetLink(null);
    setCopied(false);
    setSavingId(user.id);
    try {
      setResetLink((await createResetLink(user.id)).data);
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      setError(typeof detail === "string" ? detail : `Could not create a reset link for ${user.email}.`);
    } finally {
      setSavingId(null);
    }
  };

  const copyResetLink = async () => {
    if (!resetLink) return;
    try {
      await navigator.clipboard.writeText(resetLink.url);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  if (loadFailed) {
    return (
      <Layout variant="admin">
        <h1 className="mb-7 text-4xl font-extrabold tracking-tight">Platform overview</h1>
        <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-red-800">
          The admin data could not be loaded. Check that the API is running, then reload the page.
        </p>
      </Layout>
    );
  }
  if (!overview) {
    return (
      <Layout variant="admin">
        <h1 className="mb-7 text-4xl font-extrabold tracking-tight">Platform overview</h1>
        <LoadingSpinner />
      </Layout>
    );
  }

  const v = overview.open_vulnerabilities;

  return (
    <Layout variant="admin">
      <h1 className="text-4xl font-extrabold tracking-tight">Platform overview</h1>
      <p className="mb-7 mt-1 text-body">Every user and scan on Wiseflow.</p>

      <dl className="mb-7 grid overflow-hidden rounded-2xl border-2 border-ink bg-white shadow-hard-ink sm:grid-cols-2 lg:grid-cols-5">
        <Stat label="Users" value={overview.users_total} note={`${overview.users_active} active, ${overview.super_admins} super admin`} />
        <Stat label="Projects" value={overview.projects_total} note={`${overview.scans_total} scans in all`} />
        <Stat label="Scans today" value={overview.scans_today} note={`${overview.scans_running} running, ${overview.scans_queued} queued`} />
        <Stat
          label="Failed scans today"
          value={overview.scans_failed_today}
          note="Scans that ended in an error"
          tone={overview.scans_failed_today > 0 ? "bad" : undefined}
        />
        <Stat label="Critical findings open" value={v.critical} note={`${v.high} high, across all users`} tone={v.critical > 0 ? "bad" : undefined} />
      </dl>

      {error && (
        <p role="alert" className="mb-5 rounded-xl border border-red-200 bg-red-50 px-5 py-3 text-red-800">
          {error}
        </p>
      )}

      {resetLink && (
        <section role="status" className="mb-5 flex flex-col gap-3 rounded-2xl border-2 border-ink bg-white p-5 shadow-hard-ink">
          <div>
            <h2 className="text-lg font-bold">Password reset link for {resetLink.email}</h2>
            <p className="text-body">
              Send this to them yourself. It works once, expires at {new Date(resetLink.expires_at).toLocaleTimeString()} and is
              not shown again.
            </p>
          </div>
          <code className="break-all rounded-[10px] bg-soft px-3.5 py-3 font-mono text-[13.5px]">{resetLink.url}</code>
          <div className="flex flex-wrap gap-2.5">
            <button type="button" onClick={copyResetLink} className="h-11 rounded-[10px] bg-ink px-4 text-sm font-bold text-white">
              {copied ? "Copied" : "Copy link"}
            </button>
            <button type="button" onClick={() => setResetLink(null)} className="h-11 rounded-[10px] border-[1.5px] border-ink bg-white px-4 text-sm font-semibold">
              Done
            </button>
          </div>
        </section>
      )}

      <section className="mb-7 overflow-hidden rounded-2xl border border-gray-300 bg-white">
        <h2 className="px-5 py-4 text-lg font-bold">Users and roles</h2>
        <div className="relative overflow-x-auto">
          <table className="w-full min-w-[1040px] border-collapse text-left">
            <thead>
              <tr className="bg-soft text-[13.5px] text-body">
                <th scope="col" className="px-5 py-2.5 font-semibold">User</th>
                <th scope="col" className="px-3 py-2.5 font-semibold">Organisation</th>
                <th scope="col" className="px-3 py-2.5 font-semibold">Platform role</th>
                <th scope="col" className="px-3 py-2.5 font-semibold">Projects</th>
                <th scope="col" className="px-3 py-2.5 font-semibold">Scans</th>
                <th scope="col" className="px-3 py-2.5 font-semibold">Joined</th>
                <th scope="col" className="px-5 py-2.5 font-semibold">Access</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const self = u.id === me?.id;
                const busy = savingId === u.id;
                return (
                  <tr key={u.id} className="border-t border-line">
                    <td className="px-5 py-3">
                      <div className="font-semibold">
                        {u.full_name}
                        {self && <span className="ml-2 rounded bg-brand-50 px-1.5 py-0.5 text-xs font-bold text-brand-700">You</span>}
                      </div>
                      <div className="text-[13.5px] text-body break-all">{u.email}</div>
                    </td>
                    <td className="px-3 py-3">
                      <div>{u.organization_name ?? "None yet"}</div>
                      {u.org_role && <div className="text-[13.5px] capitalize text-body">{u.org_role}</div>}
                    </td>
                    <td className="px-3 py-3">
                      <label className="sr-only" htmlFor={`role-${u.id}`}>
                        Role for {u.email}
                      </label>
                      <select
                        id={`role-${u.id}`}
                        value={u.role}
                        disabled={self || busy}
                        onChange={(e) => change(u, { role: e.target.value as UserRole })}
                        className="h-11 rounded-[10px] border border-gray-400 bg-white px-2.5 text-[15px] disabled:bg-soft disabled:text-body"
                      >
                        <option value="user">User</option>
                        <option value="super_admin">Super admin</option>
                      </select>
                    </td>
                    <td className="px-3 py-3">{u.project_count}</td>
                    <td className="px-3 py-3">{u.scan_count}</td>
                    <td className="px-3 py-3 whitespace-nowrap text-body">{new Date(u.created_at).toLocaleDateString()}</td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3">
                        <span
                          className={`whitespace-nowrap rounded-full px-2.5 py-1 text-[13px] font-bold ${
                            u.is_active ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-800"
                          }`}
                        >
                          {u.is_active ? "Active" : "Deactivated"}
                        </span>
                        {!self && (
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => change(u, { is_active: !u.is_active })}
                            className="h-11 rounded-[10px] border-[1.5px] border-ink bg-white px-3.5 text-sm font-semibold disabled:opacity-50"
                          >
                            {u.is_active ? "Deactivate" : "Reactivate"}
                          </button>
                        )}
                        {u.is_active && (
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => makeResetLink(u)}
                            aria-label={`Create a password reset link for ${u.email}`}
                            className="h-11 whitespace-nowrap rounded-[10px] border-[1.5px] border-gray-400 bg-white px-3.5 text-sm font-semibold disabled:opacity-50"
                          >
                            Reset link
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="overflow-hidden rounded-2xl border border-gray-300 bg-white">
        <h2 className="px-5 py-4 text-lg font-bold">Latest scans, all users</h2>
        {scans.length === 0 ? (
          <p className="border-t border-line px-5 py-4 text-body">No scans have been run yet.</p>
        ) : (
          <div className="relative overflow-x-auto">
            <table className="w-full min-w-[640px] border-collapse text-left">
              <thead>
                <tr className="bg-soft text-[13.5px] text-body">
                  <th scope="col" className="px-5 py-2.5 font-semibold">App</th>
                  <th scope="col" className="px-3 py-2.5 font-semibold">Run by</th>
                  <th scope="col" className="px-3 py-2.5 font-semibold">Status</th>
                  <th scope="col" className="px-5 py-2.5 font-semibold">Started</th>
                </tr>
              </thead>
              <tbody>
                {scans.map((s) => (
                  <tr key={s.id} className="border-t border-line">
                    <td className="px-5 py-3 font-mono text-sm break-all">{s.url}</td>
                    <td className="px-3 py-3 text-body break-all">{s.owner_email}</td>
                    <td className="px-3 py-3">
                      <StatusPill status={s.status} progress={s.progress} />
                    </td>
                    <td className="px-5 py-3 whitespace-nowrap text-body">{new Date(s.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </Layout>
  );
}
