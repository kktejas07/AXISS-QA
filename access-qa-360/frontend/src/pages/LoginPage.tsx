import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { login } from "../api/auth";
import { AuthAlert, AuthCard, authButton, authField } from "../components/AuthCard";
import { SsoButtons } from "../components/SsoButtons";
import { clearMe } from "../hooks/useMe";

// Why a Google or Microsoft sign-in did not finish, in plain words.
const ssoErrors: Record<string, string> = {
  cancelled: "The sign-in was cancelled. Try again when you are ready.",
  expired: "That sign-in took too long or was started in another browser. Try again.",
  failed: "The sign-in could not be completed. Try again, or use your email and password.",
  unavailable: "That way of signing in is not switched on for this Wiseflow server.",
  unverified: "Your Google account's email address is not verified, so it cannot be used to sign in.",
  no_email: "That account did not share an email address, so it cannot be used to sign in.",
  deactivated: "This account has been deactivated. Contact your administrator.",
  invite_mismatch: "That invitation is for a different email address. Sign in with the address it was sent to.",
  no_seats: "That organisation has no free seats. Ask its owner to make room.",
};

export function LoginPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState(params.get("email") ?? "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const res = await login(email.trim(), password);
      clearMe();
      localStorage.setItem("token", res.data.access_token);
      navigate("/");
    } catch (err) {
      const status = (err as { response?: { status?: number } }).response?.status;
      setError(
        status === 401
          ? "That email and password do not match an account."
          : status === 403
            ? "This account has been deactivated. Contact your administrator."
            : "Could not sign in. Check your connection and try again."
      );
      setBusy(false);
    }
  };

  return (
    <AuthCard title="Sign in" intro="Welcome back to your workspace.">
      {params.get("reset") && !error && <AuthAlert tone="ok">Your password was changed. Sign in with the new one.</AuthAlert>}
      {error && <AuthAlert>{error}</AuthAlert>}
      {!error && params.get("sso_error") && <AuthAlert>{ssoErrors[params.get("sso_error") ?? ""] ?? ssoErrors.failed}</AuthAlert>}
      <SsoButtons />
      <form onSubmit={submit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1.5 text-sm font-semibold">
          Email
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" className={authField} />
        </label>
        <div className="flex flex-col gap-1.5">
          <div className="flex items-baseline justify-between gap-3">
            <label htmlFor="password" className="text-sm font-semibold">Password</label>
            <Link to="/forgot-password" className="text-sm font-semibold text-brand-600">Forgot password?</Link>
          </div>
          <input id="password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" className={authField} />
        </div>
        <button type="submit" disabled={busy} className={authButton}>
          {busy ? "Signing in" : "Sign in"}
        </button>
      </form>
      <p className="mt-5 text-center text-sm text-body">
        No account yet?{" "}
        <Link to="/register" className="font-semibold text-brand-600">
          Create one
        </Link>
      </p>
    </AuthCard>
  );
}
