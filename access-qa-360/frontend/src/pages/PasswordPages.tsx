import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { checkResetLink, forgotPassword, resetPassword } from "../api/auth";
import { AuthAlert, AuthCard, authButton, authField } from "../components/AuthCard";
import { apiError } from "../utils/errors";

const back = (
  <p className="mt-5 text-center text-sm text-body">
    <Link to="/login" className="font-semibold text-brand-600">
      Back to sign in
    </Link>
  </p>
);

/** Ask for a reset link by email. */
export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [delivery, setDelivery] = useState<"email" | "admin" | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      setDelivery((await forgotPassword(email.trim())).data.delivery);
    } catch (err) {
      setError(apiError(err, "Could not send the request. Check your connection and try again."));
    } finally {
      setBusy(false);
    }
  };

  if (delivery === "email") {
    return (
      <AuthCard title="Check your email">
        <p>
          If <span className="break-all font-semibold">{email.trim()}</span> has a Wiseflow account, a link to choose a new
          password is on its way. It works once and expires in an hour.
        </p>
        <p className="mt-3 text-body">Nothing after a few minutes? Check spam, or ask for another link.</p>
        <button type="button" onClick={() => setDelivery(null)} className="mt-5 h-12 w-full rounded-[10px] border-[1.5px] border-ink bg-white font-semibold">
          Send another link
        </button>
        {back}
      </AuthCard>
    );
  }
  if (delivery === "admin") {
    return (
      <AuthCard title="Ask your administrator">
        <p>This Wiseflow server does not send email, so a reset link cannot be emailed to you.</p>
        <p className="mt-3">Ask your Wiseflow administrator for a password reset link. They can create one from the admin console.</p>
        {back}
      </AuthCard>
    );
  }

  return (
    <AuthCard title="Forgot your password?" intro="Enter your email and we will send a link to choose a new one.">
      {error && <AuthAlert>{error}</AuthAlert>}
      <form onSubmit={submit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1.5 text-sm font-semibold">
          Email
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" className={authField} />
        </label>
        <button type="submit" disabled={busy} className={authButton}>
          {busy ? "Sending" : "Send reset link"}
        </button>
      </form>
      {back}
    </AuthCard>
  );
}

/** Choose a new password from a reset link: /reset-password?token=... */
export function ResetPasswordPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [account, setAccount] = useState<string | null>(null);
  const [gone, setGone] = useState(!token);
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) return;
    checkResetLink(token)
      .then((r) => setAccount(r.data.email))
      .catch(() => setGone(true));
  }, [token]);

  if (gone) {
    return (
      <AuthCard title="This link no longer works">
        <p>Reset links work once and expire after an hour. Ask for a new one to continue.</p>
        <Link to="/forgot-password" className={`${authButton} mt-5 flex items-center justify-center`}>
          Get a new link
        </Link>
        {back}
      </AuthCard>
    );
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password !== again) {
      setError("The two passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      const { data } = await resetPassword(token, password);
      navigate(`/login?reset=1&email=${encodeURIComponent(data.email)}`, { replace: true });
    } catch (err) {
      setError(apiError(err, "Could not change the password. Try again."));
      setBusy(false);
    }
  };

  return (
    <AuthCard title="Choose a new password" intro={account ? <>For <span className="break-all font-semibold text-ink">{account}</span>. Other devices will be signed out.</> : "Checking your link"}>
      {error && <AuthAlert>{error}</AuthAlert>}
      <form onSubmit={submit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1.5 text-sm font-semibold">
          New password
          <input type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" className={authField} />
          <span className="font-normal text-body">At least 8 characters.</span>
        </label>
        <label className="flex flex-col gap-1.5 text-sm font-semibold">
          Repeat new password
          <input type="password" required minLength={8} value={again} onChange={(e) => setAgain(e.target.value)} autoComplete="new-password" className={authField} />
        </label>
        <button type="submit" disabled={busy || !account} className={authButton}>
          {busy ? "Saving" : "Save new password"}
        </button>
      </form>
      {back}
    </AuthCard>
  );
}
