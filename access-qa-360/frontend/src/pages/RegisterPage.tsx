import { TechBackdrop } from "../components/TechBackdrop";
import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Logo } from "../components/Logo";
import { SsoButtons } from "../components/SsoButtons";
import { login, previewInvite, register } from "../api/auth";
import { clearMe } from "../hooks/useMe";
import { apiError } from "../utils/errors";

const roleName: Record<string, string> = { admin: "an admin", member: "a member", viewer: "a viewer" };
const field = "h-12 w-full rounded-[10px] border border-gray-400 bg-white px-3.5 text-[15px] disabled:bg-soft disabled:text-body";

/** Sign-up. With ?invite=<token> the new account joins the inviting organisation. */
export function RegisterPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = params.get("invite") ?? undefined;
  const [invite, setInvite] = useState<{ organization_name: string; email: string; role: string } | null>(null);
  const [inviteGone, setInviteGone] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) return;
    previewInvite(token)
      .then((r) => {
        setInvite(r.data);
        setEmail(r.data.email);
      })
      .catch(() => setInviteGone(true));
  }, [token]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await register(email.trim(), password, name.trim(), invite ? token : undefined);
      const res = await login(email.trim(), password);
      clearMe();
      localStorage.setItem("token", res.data.access_token);
      navigate("/");
    } catch (err) {
      setError(apiError(err, "Could not create the account. Try again."));
      setBusy(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-soft p-4 font-sans text-ink">
      <TechBackdrop variant="auth" />
      <div className="relative w-full max-w-md rounded-2xl border-2 border-ink bg-white p-8 shadow-hard">
        <div className="mb-6">
          <Logo />
        </div>

        <h1 className="text-2xl font-extrabold tracking-tight">
          {invite ? `Join ${invite.organization_name}` : "Create your account"}
        </h1>
        <p className="mb-6 mt-1 text-body">
          {invite
            ? `You have been invited as ${roleName[invite.role] ?? invite.role}. You will see the organisation's scans as soon as you sign up.`
            : "Free to start: your own workspace, no card needed. You can invite a team later."}
        </p>

        {inviteGone && (
          <p role="alert" className="mb-4 rounded-[10px] border border-orange-200 bg-orange-50 px-4 py-3 text-orange-900">
            This invitation link is no longer valid. Ask for a new one, or sign up for your own workspace below.
          </p>
        )}
        {error && (
          <p role="alert" className="mb-4 rounded-[10px] border border-red-200 bg-red-50 px-4 py-3 text-red-800">
            {error}
          </p>
        )}

        <SsoButtons invite={invite ? token : undefined} />
        <form onSubmit={submit} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1.5 text-sm font-semibold">
            Full name
            <input type="text" required value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" className={field} />
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-semibold">
            Work email
            <input
              type="email"
              required
              value={email}
              disabled={!!invite}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              className={field}
            />
            {invite && <span className="font-normal text-body">The invitation is for this address.</span>}
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-semibold">
            Password
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              className={field}
            />
            <span className="font-normal text-body">At least 8 characters.</span>
          </label>
          <button type="submit" disabled={busy} className="h-[52px] rounded-[10px] bg-brand-600 font-bold text-white hover:bg-brand-700 disabled:opacity-60">
            {busy ? "Creating account" : invite ? "Join organisation" : "Create account"}
          </button>
        </form>

        <p className="mt-5 text-center text-sm text-body">
          Already have an account?{" "}
          <Link to="/login" className="font-semibold text-brand-600">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
