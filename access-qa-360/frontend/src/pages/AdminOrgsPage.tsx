import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Layout } from "../components/Layout";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { getAdminOrg, getAdminOrgs, getAuditLog, updateAdminOrg } from "../api/admin";
import type { AccountType, AdminOrg, AuditLogEntry } from "../types";
import { apiError } from "../utils/errors";

const accountName: Record<AccountType, string> = { individual: "Individual", team: "Team", enterprise: "Enterprise" };
const roleName: Record<string, string> = { owner: "Owner", admin: "Admin", member: "Member", viewer: "Viewer" };
const card = "overflow-hidden rounded-2xl border border-gray-300 bg-white";
const input = "h-12 rounded-[10px] border border-gray-400 bg-white px-3.5 text-[15px]";
const th = "px-4 py-2.5 font-semibold";

const of = (used: number, max: number | null) => (max === null ? `${used}, no limit` : `${used} of ${max}`);

function OrgStatus({ status }: { status: string }) {
  return (
    <span className={`inline-block whitespace-nowrap rounded-full px-2.5 py-1 text-[13px] font-bold ${status === "active" ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-800"}`}>
      {status === "active" ? "Active" : "Suspended"}
    </span>
  );
}

function Failed({ title }: { title: string }) {
  return (
    <Layout variant="admin">
      <h1 className="mb-7 text-4xl font-extrabold tracking-tight">{title}</h1>
      <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-red-800">
        This could not be loaded. Check that the API is running, then reload the page.
      </p>
    </Layout>
  );
}

/** Every organisation on the platform. */
export function AdminOrgsPage() {
  const [orgs, setOrgs] = useState<AdminOrg[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [query, setQuery] = useState("");
  const [type, setType] = useState<"all" | AccountType>("all");

  useEffect(() => {
    getAdminOrgs()
      .then((r) => setOrgs(r.data))
      .catch(() => setFailed(true));
  }, []);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (orgs ?? []).filter(
      (o) => (type === "all" || o.account_type === type) && (!q || o.name.toLowerCase().includes(q) || (o.owner_email ?? "").toLowerCase().includes(q))
    );
  }, [orgs, query, type]);

  if (failed) return <Failed title="Organisations" />;

  return (
    <Layout variant="admin">
      <h1 className="text-4xl font-extrabold tracking-tight">Organisations</h1>
      <p className="mb-7 mt-1 text-body">{orgs ? `${orgs.length} on Wiseflow` : "Loading"}</p>

      <div className="mb-5 flex flex-wrap gap-3">
        <label className="flex min-w-0 flex-[1_1_260px] flex-col gap-1.5 text-[13.5px] font-semibold text-body">
          Search
          <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Name or owner email" className={`${input} w-full text-ink`} />
        </label>
        <label className="flex flex-col gap-1.5 text-[13.5px] font-semibold text-body">
          Account type
          <select value={type} onChange={(e) => setType(e.target.value as "all" | AccountType)} className={`${input} px-2.5 text-ink`}>
            <option value="all">All types</option>
            <option value="individual">Individual</option>
            <option value="team">Team</option>
            <option value="enterprise">Enterprise</option>
          </select>
        </label>
      </div>

      {!orgs ? (
        <LoadingSpinner />
      ) : shown.length === 0 ? (
        <p className="rounded-2xl border border-gray-300 bg-white px-6 py-10 text-center text-body">No organisations match.</p>
      ) : (
        <section className={card}>
          <div className="relative overflow-x-auto">
            <table className="w-full min-w-[760px] border-collapse text-left">
              <thead>
                <tr className="bg-soft text-[13.5px] text-body">
                  <th scope="col" className={th}>Organisation</th>
                  <th scope="col" className={th}>Account type</th>
                  <th scope="col" className={th}>Seats</th>
                  <th scope="col" className={th}>Scans this month</th>
                  <th scope="col" className={th}>Status</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((o) => (
                  <tr key={o.id} className="border-t border-line">
                    <td className="px-4 py-3">
                      <Link to={`/admin/organizations/${o.id}`} className="font-semibold text-brand-600 hover:text-brand-700">{o.name}</Link>
                      <div className="break-all text-[13.5px] text-body">{o.owner_email ?? "No owner"}</div>
                    </td>
                    <td className="px-4 py-3">{accountName[o.account_type]}</td>
                    <td className="px-4 py-3">{of(o.member_count, o.seat_limit)}</td>
                    <td className="px-4 py-3">{of(o.scans_this_month, o.scan_limit)}</td>
                    <td className="px-4 py-3"><OrgStatus status={o.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </Layout>
  );
}

/** One organisation: account type, limits, status and members. */
export function AdminOrgDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [org, setOrg] = useState<AdminOrg | null>(null);
  const [failed, setFailed] = useState(false);
  const [type, setType] = useState<AccountType>("individual");
  const [seats, setSeats] = useState("");
  const [scans, setScans] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const show = (o: AdminOrg) => {
    setOrg(o);
    setType(o.account_type);
    setSeats(o.seat_limit === null ? "" : String(o.seat_limit));
    setScans(o.scan_limit === null ? "" : String(o.scan_limit));
  };

  useEffect(() => {
    if (id) getAdminOrg(id).then((r) => show(r.data)).catch(() => setFailed(true));
  }, [id]);

  if (failed) return <Failed title="Organisation" />;
  if (!org || !id) {
    return (
      <Layout variant="admin">
        <LoadingSpinner />
      </Layout>
    );
  }

  const save = async (changes: Parameters<typeof updateAdminOrg>[1], done: string) => {
    setError("");
    setNotice("");
    setBusy(true);
    try {
      show((await updateAdminOrg(id, changes)).data);
      setNotice(done);
    } catch (e) {
      setError(apiError(e, "The change could not be saved."));
    } finally {
      setBusy(false);
    }
  };

  const toLimit = (text: string) => (text.trim() === "" ? null : Number(text));
  const typeChanged = type !== org.account_type;

  return (
    <Layout variant="admin">
      <Link to="/admin/organizations" className="text-sm font-semibold text-brand-600">Organisations</Link>
      <div className="mb-7 mt-1 flex flex-wrap items-center gap-3">
        <h1 className="text-4xl font-extrabold tracking-tight">{org.name}</h1>
        <OrgStatus status={org.status} />
      </div>

      {error && <p role="alert" className="mb-6 rounded-xl border border-red-200 bg-red-50 px-5 py-3 text-red-800">{error}</p>}
      {notice && <p role="status" className="mb-6 rounded-xl border border-emerald-200 bg-emerald-50 px-5 py-3 text-emerald-900">{notice}</p>}

      <dl className="mb-7 grid overflow-hidden rounded-2xl border-2 border-ink bg-white shadow-hard-ink sm:grid-cols-3">
        {[
          ["Members", of(org.member_count, org.seat_limit)],
          ["Scans this month", of(org.scans_this_month, org.scan_limit)],
          ["Created", new Date(org.created_at).toLocaleDateString()],
        ].map(([label, value]) => (
          <div key={label} className="border-b border-line px-6 py-5 last:border-b-0 sm:border-b-0 sm:border-r sm:last:border-r-0">
            <dt className="text-sm font-semibold text-body">{label}</dt>
            <dd className="text-[28px] font-extrabold leading-tight">{value}</dd>
          </div>
        ))}
      </dl>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          // Changing the account type resets seats to that type's default unless seats were edited too.
          const seatsEdited = seats !== (org.seat_limit === null ? "" : String(org.seat_limit));
          save(
            { ...(typeChanged ? { account_type: type } : {}), ...(!typeChanged || seatsEdited ? { seat_limit: toLimit(seats) } : {}), scan_limit: toLimit(scans) },
            "Plan and limits saved."
          );
        }}
        className="mb-7 flex flex-col gap-4 rounded-2xl border border-gray-300 bg-white p-6"
      >
        <div>
          <h2 className="text-lg font-bold">Plan and limits</h2>
          <p className="text-body">Leave a limit empty for no limit. Changes are written to the audit log.</p>
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <label className="flex flex-col gap-1.5 text-sm font-semibold">
            Account type
            <select value={type} onChange={(e) => setType(e.target.value as AccountType)} className={`${input} px-2.5`}>
              <option value="individual">Individual</option>
              <option value="team">Team</option>
              <option value="enterprise">Enterprise</option>
            </select>
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-semibold">
            Seat limit
            <input type="number" min={1} value={seats} onChange={(e) => setSeats(e.target.value)} placeholder="No limit" className={input} />
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-semibold">
            Scans per month
            <input type="number" min={1} value={scans} onChange={(e) => setScans(e.target.value)} placeholder="No limit" className={input} />
          </label>
        </div>
        <button type="submit" disabled={busy} className="h-12 self-start rounded-[10px] bg-brand-600 px-5 font-bold text-white hover:bg-brand-700 disabled:opacity-60">
          Save plan and limits
        </button>
      </form>

      <section className={`${card} mb-7`}>
        <h2 className="px-5 py-4 text-lg font-bold">Members</h2>
        <div className="relative overflow-x-auto">
          <table className="w-full min-w-[520px] border-collapse text-left">
            <thead>
              <tr className="bg-soft text-[13.5px] text-body">
                <th scope="col" className={th}>Person</th>
                <th scope="col" className={th}>Role</th>
                <th scope="col" className={th}>Account</th>
              </tr>
            </thead>
            <tbody>
              {(org.members ?? []).map((m) => (
                <tr key={m.id} className="border-t border-line">
                  <td className="px-4 py-3">
                    <div className="font-semibold">{m.full_name}</div>
                    <div className="break-all text-[13.5px] text-body">{m.email}</div>
                  </td>
                  <td className="px-4 py-3">{roleName[m.org_role] ?? m.org_role}</td>
                  <td className="px-4 py-3">{m.is_active ? "Active" : "Deactivated"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className={`flex flex-col gap-3 rounded-2xl border-[1.5px] bg-white p-6 ${org.status === "active" ? "border-red-700" : "border-gray-300"}`}>
        <div>
          <h2 className="text-lg font-bold">{org.status === "active" ? "Suspend this organisation" : "Reactivate this organisation"}</h2>
          <p className="text-body">
            {org.status === "active"
              ? "Members keep access to existing results, but nobody can start a new scan."
              : "Members will be able to start scans again."}
          </p>
        </div>
        <button
          type="button"
          disabled={busy}
          onClick={() =>
            org.status === "active"
              ? save({ status: "suspended" }, "Organisation suspended.")
              : save({ status: "active" }, "Organisation reactivated.")
          }
          className={`h-12 self-start rounded-[10px] border-[1.5px] bg-white px-5 font-semibold disabled:opacity-60 ${org.status === "active" ? "border-red-700 text-red-800" : "border-ink text-ink"}`}
        >
          {org.status === "active" ? "Suspend organisation" : "Reactivate organisation"}
        </button>
      </section>
    </Layout>
  );
}

const actionName: Record<string, string> = {
  "user.role": "Changed platform role",
  "user.deactivate": "Deactivated account",
  "user.reactivate": "Reactivated account",
  "org.account_type": "Changed account type",
  "org.seat_limit": "Changed seat limit",
  "org.scan_limit": "Changed monthly scan limit",
  "org.suspend": "Suspended organisation",
  "org.reactivate": "Reactivated organisation",
};

/** What super admins changed, newest first. */
export function AdminAuditPage() {
  const [entries, setEntries] = useState<AuditLogEntry[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    getAuditLog()
      .then((r) => setEntries(r.data))
      .catch(() => setFailed(true));
  }, []);

  if (failed) return <Failed title="Audit log" />;

  return (
    <Layout variant="admin">
      <h1 className="text-4xl font-extrabold tracking-tight">Audit log</h1>
      <p className="mb-7 mt-1 text-body">Every change a super admin makes to an account or organisation, newest first.</p>
      {!entries ? (
        <LoadingSpinner />
      ) : entries.length === 0 ? (
        <p className="rounded-2xl border border-gray-300 bg-white px-6 py-10 text-center text-body">No admin changes have been made yet.</p>
      ) : (
        <section className={card}>
          <div className="relative overflow-x-auto">
            <table className="w-full min-w-[720px] border-collapse text-left">
              <thead>
                <tr className="bg-soft text-[13.5px] text-body">
                  <th scope="col" className={th}>When</th>
                  <th scope="col" className={th}>Who</th>
                  <th scope="col" className={th}>Action</th>
                  <th scope="col" className={th}>On</th>
                  <th scope="col" className={th}>Change</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e) => (
                  <tr key={e.id} className="border-t border-line">
                    <td className="whitespace-nowrap px-4 py-3 text-body">{new Date(e.created_at).toLocaleString()}</td>
                    <td className="break-all px-4 py-3 font-semibold">{e.actor_email}</td>
                    <td className="px-4 py-3">{actionName[e.action] ?? e.action}</td>
                    <td className="break-all px-4 py-3">{e.target}</td>
                    <td className="px-4 py-3 text-body">{e.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </Layout>
  );
}
