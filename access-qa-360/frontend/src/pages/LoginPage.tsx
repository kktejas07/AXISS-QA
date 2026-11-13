import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { login } from "../api/auth";
import { AuthAlert, AuthCard, authButton, authField } from "../components/AuthCard";
import { clearMe } from "../hooks/useMe";

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
