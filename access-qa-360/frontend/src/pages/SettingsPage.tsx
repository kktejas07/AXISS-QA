import { useEffect, useState } from "react";
import { Check, Copy, Minus } from "lucide-react";
import { Layout } from "../components/Layout";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { cancelInvite, changeRole, createInvite, getInvites, getMembers, getOrg, removeMember, renameOrg } from "../api/org";
import { changePassword } from "../api/auth";
import { ApiKeysSection, JiraSection } from "../components/IntegrationSettings";
import { BillingSection } from "../components/BillingSection";
import { ConnectionsSection } from "../components/ConnectionsSection";
import { AiSettingsSection } from "../components/AiSettings";
import { WiseDocuments } from "../components/Wise";
import { RequireSsoSection, TwoStepSection } from "../components/SecuritySettings";
import { clearMe, useMe } from "../hooks/useMe";
import type { Invite, Member, Org, OrgRole } from "../types";
import { apiError } from "../utils/errors";

const roleName: Record<OrgRole, string> = { owner: "Owner", admin: "Admin", member: "Member", viewer: "Viewer" };
const accountName = { individual: "Individual", team: "Team", enterprise: "Enterprise" } as const;
const roles: OrgRole[] = ["owner", "admin", "member", "viewer"];

// Mirrors PERMISSIONS in the API (backend/app/services/orgs.py).
const matrix: { label: string; allowed: OrgRole[] }[] = [
  { label: "See scans, findings and downloads", allowed: ["owner", "admin", "member", "viewer"] },
  { label: "Create and start scans", allowed: ["owner", "admin", "member"] },
  { label: "Invite people, change roles, remove people", allowed: ["owner", "admin"] },
  { label: "Create Jira issues from findings", allowed: ["owner", "admin", "member"] },
  { label: "Rename the organisation, manage API keys and Jira", allowed: ["owner", "admin"] },
  { label: "Transfer ownership", allowed: ["owner"] },
];

const card = "overflow-hidden rounded-2xl border border-gray-300 bg-white";
const input = "h-12 rounded-[10px] border border-gray-400 bg-white px-3.5 text-[15px]";
const quietButton = "h-11 rounded-[10px] border-[1.5px] border-gray-400 bg-white px-3.5 text-sm font-semibold disabled:opacity-50";

const limit = (used: number, max: number | null) => (max === null ? `${used}, no limit` : `${used} of ${max}`);

/** Organisation details, the team and their roles, and invitations. */
export function SettingsPage() {
  const me = useMe();
  const [org, setOrg] = useState<Org | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [invites, setInvites] = useState<Invite[]>([]);
  const [loadFailed, setLoadFailed] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [name, setName] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<OrgRole>("member");
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");

  const load = async () => {
    const o = (await getOrg()).data;
    setOrg(o);
    setName(o.name);
    setMembers((await getMembers()).data);
    setInvites(o.permissions.includes("members.manage") ? (await getInvites()).data : []);
  };

  useEffect(() => {
    load().catch(() => setLoadFailed(true));
  }, []);

  /** Run a change, show the server's reason if it is refused, then reload. */
  const run = async (action: () => Promise<unknown>, done: string | (() => string), fallback: string) => {
    setError("");
    setNotice("");
    setBusy(true);
    try {
      await action();
      await load();
      setNotice(typeof done === "string" ? done : done());
    } catch (e) {
      setError(apiError(e, fallback));
    } finally {
      setBusy(false);
    }
  };

  if (loadFailed) {
    return (
      <Layout>
        <h1 className="mb-7 text-4xl font-extrabold tracking-tight">Settings</h1>
        <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-red-800">
          Settings could not be loaded. Check that the API is running, then reload the page.
        </p>
      </Layout>
    );
  }
  if (!org || !me) {
    return (
      <Layout>
        <h1 className="mb-7 text-4xl font-extrabold tracking-tight">Settings</h1>
        <LoadingSpinner />
      </Layout>
    );
  }

  const canManage = org.permissions.includes("members.manage");
  const canEdit = org.permissions.includes("org.edit");
  const isOwner = org.my_role === "owner";
  const inviteLink = (token: string) => `${window.location.origin}/register?invite=${token}`;

  const copy = async (token: string) => {
    try {
      await navigator.clipboard.writeText(inviteLink(token));
      setCopied(token);
      setTimeout(() => setCopied(null), 2000);
    } catch {
      setError("Could not copy. Select the link and copy it yourself.");
    }
  };

  const roleChoices = (m: Member): OrgRole[] => (isOwner ? roles : roles.filter((r) => r !== "owner" || m.org_role === "owner"));

  return (
    <Layout>
      <h1 className="mb-7 text-4xl font-extrabold tracking-tight">Settings</h1>

      {org.status === "suspended" && (
        <p role="alert" className="mb-6 rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-red-800">
          This organisation is suspended. Existing results stay available, but new scans cannot start. Contact support.
        </p>
      )}
      {error && (
        <p role="alert" className="mb-6 rounded-xl border border-red-200 bg-red-50 px-5 py-3 text-red-800">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="mb-6 rounded-xl border border-emerald-200 bg-emerald-50 px-5 py-3 text-emerald-900">
          {notice}
        </p>
      )}

      <div className="flex flex-col gap-7">
        {/* Organisation */}
        <section className="rounded-2xl border-2 border-ink bg-white p-6 shadow-hard">
          <h2 className="mb-4 text-lg font-bold">Organisation</h2>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              run(async () => {
                await renameOrg(name);
                clearMe();
              }, "Organisation renamed.", "Could not rename the organisation.");
            }}
            className="mb-5 flex flex-wrap items-end gap-3"
          >
            <label className="flex min-w-0 flex-[1_1_280px] flex-col gap-1.5 text-sm font-semibold">
              Name
              <input value={name} onChange={(e) => setName(e.target.value)} disabled={!canEdit} required maxLength={120} className={`${input} w-full disabled:bg-soft disabled:text-body`} />
            </label>
            {canEdit && (
              <button type="submit" disabled={busy || name.trim() === org.name} className="h-12 rounded-[10px] bg-ink px-5 font-bold text-white disabled:opacity-50">
                Save name
              </button>
            )}
          </form>
          <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <dt className="text-[13.5px] font-semibold text-body">Account type</dt>
              <dd className="text-xl font-bold">{accountName[org.account_type]}</dd>
            </div>
            <div>
              <dt className="text-[13.5px] font-semibold text-body">Seats used</dt>
              <dd className="text-xl font-bold">{limit(org.seats_used, org.seat_limit)}</dd>
            </div>
            <div>
              <dt className="text-[13.5px] font-semibold text-body">Scans this month</dt>
              <dd className="text-xl font-bold">{limit(org.scans_this_month, org.scan_limit)}</dd>
            </div>
            <div>
              <dt className="text-[13.5px] font-semibold text-body">Your role</dt>
              <dd className="text-xl font-bold">{roleName[org.my_role]}</dd>
            </div>
          </dl>
          {org.account_type === "individual" && (
            <p className="mt-4 text-[14.5px] text-body">
              Individual accounts have one seat. To invite a team, ask Wiseflow support to move this organisation to a Team account.
            </p>
          )}
        </section>

        {/* Team */}
        <section className={card}>
          <h2 className="px-5 py-4 text-lg font-bold">Team and roles</h2>
          <div className="relative overflow-x-auto">
            <table className="w-full min-w-[640px] border-collapse text-left">
              <thead>
                <tr className="bg-soft text-[13.5px] text-body">
                  <th scope="col" className="px-5 py-2.5 font-semibold">Person</th>
                  <th scope="col" className="px-3 py-2.5 font-semibold">Role</th>
                  <th scope="col" className="px-3 py-2.5 font-semibold">Joined</th>
                  <th scope="col" className="px-5 py-2.5 font-semibold"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {members.map((m) => {
                  const self = m.id === me.id;
                  // Admins cannot touch the owner; nobody changes their own role here.
                  const locked = !canManage || self || (m.org_role === "owner" && !isOwner);
                  return (
                    <tr key={m.id} className="border-t border-line">
                      <td className="px-5 py-3">
                        <div className="font-semibold">
                          {m.full_name}
                          {self && <span className="ml-2 rounded bg-brand-50 px-1.5 py-0.5 text-xs font-bold text-brand-700">You</span>}
                        </div>
                        <div className="break-all text-[13.5px] text-body">{m.email}</div>
                      </td>
                      <td className="px-3 py-3">
                        {locked ? (
                          <span>{roleName[m.org_role]}</span>
                        ) : (
                          <>
                            <label className="sr-only" htmlFor={`role-${m.id}`}>Role for {m.email}</label>
                            <select
                              id={`role-${m.id}`}
                              value={m.org_role}
                              disabled={busy}
                              onChange={(e) => {
                                const role = e.target.value as OrgRole;
                                run(
                                  async () => {
                                    await changeRole(m.id, role);
                                    if (role === "owner") clearMe();
                                  },
                                  role === "owner" ? `${m.full_name} is now the owner. You are an admin.` : `${m.full_name} is now ${role === "admin" ? "an" : "a"} ${roleName[role].toLowerCase()}.`,
                                  "Could not change the role."
                                );
                              }}
                              className="h-11 rounded-[10px] border border-gray-400 bg-white px-2.5 text-[15px]"
                            >
                              {roleChoices(m).map((r) => (
                                <option key={r} value={r}>{roleName[r]}</option>
                              ))}
                            </select>
                          </>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-3 py-3 text-body">{new Date(m.created_at).toLocaleDateString()}</td>
                      <td className="px-5 py-2 text-right">
                        {canManage && !self && m.org_role !== "owner" && (
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => run(() => removeMember(m.id), `${m.full_name} was removed.`, "Could not remove this person.")}
                            className={quietButton}
                          >
                            Remove
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
                {invites.map((i) => (
                  <tr key={i.id} className="border-t border-line bg-soft">
                    <td className="px-5 py-3">
                      <div className="font-semibold">Invited</div>
                      <div className="break-all text-[13.5px] text-body">{i.email}</div>
                    </td>
                    <td className="px-3 py-3">{roleName[i.role]}</td>
                    <td className="whitespace-nowrap px-3 py-3 text-body">Not joined yet</td>
                    <td className="px-5 py-2">
                      <div className="flex flex-wrap justify-end gap-2">
                        <button type="button" onClick={() => copy(i.token)} className={`${quietButton} flex items-center gap-2`}>
                          <Copy className="h-4 w-4" aria-hidden="true" />
                          {copied === i.token ? "Copied" : "Copy invite link"}
                        </button>
                        <button type="button" disabled={busy} onClick={() => run(() => cancelInvite(i.id), "Invitation cancelled.", "Could not cancel the invitation.")} className={quietButton}>
                          Cancel
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {canManage && org.account_type !== "individual" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                let emailed = false;
                const to = inviteEmail.trim();
                run(
                  async () => {
                    emailed = (await createInvite(to, inviteRole)).data.emailed === true;
                    setInviteEmail("");
                  },
                  () =>
                    emailed
                      ? `Invitation emailed to ${to}. You can also copy the link from the list.`
                      : "Invitation created. This server does not send email, so copy the link from the list and send it to them.",
                  "Could not create the invitation."
                );
              }}
              className="flex flex-wrap items-end gap-3 border-t border-line p-5"
            >
              <label className="flex min-w-0 flex-[1_1_260px] flex-col gap-1.5 text-sm font-semibold">
                Invite by email
                <input type="email" required value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} placeholder="name@company.com" className={`${input} w-full`} />
              </label>
              <label className="flex flex-col gap-1.5 text-sm font-semibold">
                Role
                <select value={inviteRole} onChange={(e) => setInviteRole(e.target.value as OrgRole)} className={`${input} px-2.5`}>
                  <option value="admin">Admin</option>
                  <option value="member">Member</option>
                  <option value="viewer">Viewer</option>
                </select>
              </label>
              <button type="submit" disabled={busy} className="h-12 rounded-[10px] bg-brand-600 px-5 font-bold text-white hover:bg-brand-700 disabled:opacity-60">
                Create invite link
              </button>
            </form>
          )}
        </section>

        <BillingSection />

        {canEdit && <ApiKeysSection />}
        <JiraSection canEdit={canEdit} />
        <ConnectionsSection canEdit={canEdit} />
        <WiseDocuments canEdit={canEdit} />
        <AiSettingsSection canEdit={canEdit} />

        {/* Password */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            run(
              async () => {
                // Other devices are signed out; this one continues with the fresh token.
                localStorage.setItem("token", (await changePassword(currentPassword, newPassword)).data.access_token);
                setCurrentPassword("");
                setNewPassword("");
              },
              "Password changed. Other devices have been signed out.",
              "Could not change the password."
            );
          }}
          className="flex flex-col gap-4 rounded-2xl border border-gray-300 bg-white p-6"
        >
          <div>
            <h2 className="text-lg font-bold">Your password</h2>
            <p className="text-body">For {me.email}. Changing it signs you out on every other device.</p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="flex flex-col gap-1.5 text-sm font-semibold">
              Current password
              <input type="password" required value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} autoComplete="current-password" className={`${input} w-full`} />
            </label>
            <label className="flex flex-col gap-1.5 text-sm font-semibold">
              New password
              <input type="password" required minLength={8} value={newPassword} onChange={(e) => setNewPassword(e.target.value)} autoComplete="new-password" className={`${input} w-full`} />
              <span className="font-normal text-body">At least 8 characters.</span>
            </label>
          </div>
          <button type="submit" disabled={busy} className="h-12 self-start rounded-[10px] bg-ink px-5 font-bold text-white disabled:opacity-50">
            Change password
          </button>
        </form>

        <TwoStepSection />
        {org && <RequireSsoSection org={org} onChange={setOrg} />}

        {/* Permission matrix */}
        <section className={card}>
          <h2 className="px-5 py-4 text-lg font-bold">What each role can do</h2>
          <div className="relative overflow-x-auto">
            <table className="w-full min-w-[620px] border-collapse text-left">
              <thead>
                <tr className="bg-soft text-sm">
                  <th scope="col" className="px-5 py-2.5 font-semibold text-body">Permission</th>
                  {roles.map((r) => (
                    <th key={r} scope="col" className="px-3 py-2.5 text-center font-bold">{roleName[r]}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {matrix.map((row) => (
                  <tr key={row.label} className="border-t border-line">
                    <th scope="row" className="px-5 py-3 font-medium">{row.label}</th>
                    {roles.map((r) => (
                      <td key={r} className="px-3 py-3 text-center">
                        {row.allowed.includes(r) ? (
                          <Check className="mx-auto h-5 w-5 text-brand-600" strokeWidth={3} aria-label="Yes" />
                        ) : (
                          <Minus className="mx-auto h-5 w-5 text-gray-400" aria-label="No" />
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </Layout>
  );
}
