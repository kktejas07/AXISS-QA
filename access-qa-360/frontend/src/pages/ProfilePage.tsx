import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Layout } from "../components/Layout";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { updateMyName } from "../api/auth";
import { card, errorBox, field, label, pageTitle, primaryButton } from "../components/ui";
import { clearMe, fetchMe } from "../hooks/useMe";
import type { Me } from "../types";
import { apiError } from "../utils/errors";

const roleName: Record<string, string> = { owner: "Owner", admin: "Admin", member: "Member", viewer: "Viewer" };
const planName: Record<string, string> = { individual: "Individual", team: "Team", enterprise: "Enterprise" };

/** Your own details: change your name, and see your email, role and organisation. */
export function ProfilePage() {
  const [me, setMe] = useState<Me | null>(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    fetchMe().then((u) => {
      setMe(u);
      setName(u.full_name);
    }).catch(() => setError("Your profile could not be loaded. Reload the page to try again."));
  }, []);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setNotice("");
    setBusy(true);
    try {
      const saved = (await updateMyName(name)).data.full_name;
      clearMe();                               // so the rest of the app reads the new name
      setMe(me && { ...me, full_name: saved });
      setName(saved);
      setNotice("Your name was changed.");
    } catch (err) {
      setError(apiError(err, "Your name could not be changed."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Layout>
      <h1 className={`${pageTitle} mb-7`}>Your profile</h1>
      {!me ? (
        error ? <p role="alert" className={errorBox}>{error}</p> : <LoadingSpinner />
      ) : (
        <div className="flex max-w-3xl flex-col gap-6">
          <form onSubmit={save} className={`${card} flex flex-col gap-4 p-6`}>
            <h2 className="text-lg font-bold">Your name</h2>
            <label className={label}>
              Name
              <input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} required autoComplete="name" className={field} />
            </label>
            {error && <p role="alert" className={errorBox}>{error}</p>}
            {notice && <p role="status" className="rounded-[10px] border border-emerald-200 bg-emerald-50 px-4 py-3 text-emerald-900">{notice}</p>}
            <button type="submit" disabled={busy || !name.trim() || name.trim() === me.full_name} className={`${primaryButton} self-start`}>
              {busy ? "Saving" : "Save name"}
            </button>
          </form>

          <section aria-labelledby="account" className={`${card} p-6`}>
            <h2 id="account" className="mb-3 text-lg font-bold">Your account</h2>
            <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
              {[
                ["Email", me.email],
                ["Organisation", me.organization.name],
                ["Your role", roleName[me.org_role] ?? me.org_role],
                ["Plan", planName[me.organization.account_type] ?? me.organization.account_type],
                ["Two-step sign-in", me.two_step_enabled ? "On" : "Off"],
              ].map(([term, value]) => (
                <div key={term}>
                  <dt className="text-sm font-semibold text-body">{term}</dt>
                  <dd className="break-words font-semibold">{value}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-4 text-body">
              Your email and role are changed by an owner or admin of your organisation. To change your password or turn on two-step sign-in, go to{" "}
              <Link to="/settings" className="font-semibold text-brand-600 underline hover:text-brand-700">Settings</Link>.
            </p>
          </section>
        </div>
      )}
    </Layout>
  );
}
