import { useMemo, useState } from "react";
import qrcode from "qrcode-generator";
import { twoStepDisable, twoStepEnable, twoStepSetup } from "../api/auth";
import { setRequireSso } from "../api/org";
import { clearMe, useMe } from "../hooks/useMe";
import type { Org } from "../types";
import { apiError } from "../utils/errors";
import { PhoneCode } from "./Illustrations";
import { errorBox, field, hint, label } from "./ui";

const section = "rounded-2xl border border-gray-300 bg-white p-6";
const darkButton = "h-12 rounded-[10px] bg-ink px-5 font-bold text-white disabled:opacity-50";
const quiet = "h-12 rounded-[10px] border-[1.5px] border-ink bg-white px-5 font-semibold disabled:opacity-50";
const ok = "mb-4 rounded-[10px] border border-emerald-200 bg-emerald-50 px-4 py-3 text-emerald-900";

/** The setup address as a QR code, drawn as plain SVG rectangles. */
function QrCode({ value }: { value: string }) {
  const { size, path } = useMemo(() => {
    const qr = qrcode(0, "M");
    qr.addData(value);
    qr.make();
    const n = qr.getModuleCount();
    let d = "";
    for (let row = 0; row < n; row++) for (let col = 0; col < n; col++) if (qr.isDark(row, col)) d += `M${col} ${row}h1v1h-1z`;
    return { size: n, path: d };
  }, [value]);
  return (
    <svg viewBox={`-2 -2 ${size + 4} ${size + 4}`} role="img" aria-label="QR code to scan with your authenticator app" className="h-44 w-44 flex-none rounded-xl border border-gray-300 bg-white" shapeRendering="crispEdges">
      <path d={path} fill="#101014" />
    </svg>
  );
}

/** Two-step sign-in with an authenticator app, for the signed-in person's own account. */
export function TwoStepSection() {
  const me = useMe();
  const [setup, setSetup] = useState<{ secret: string; uri: string } | null>(null);
  const [turningOff, setTurningOff] = useState(false);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const on = enabled ?? me?.two_step_enabled ?? false;

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

  const finish = (state: boolean, message: string) => {
    setEnabled(state);
    setSetup(null);
    setTurningOff(false);
    setCode("");
    setPassword("");
    setNotice(message);
    clearMe();
  };

  return (
    <section className={section}>
      <div className="flex flex-wrap items-start justify-between gap-6">
        <div className="min-w-0 flex-1">
          <h2 className="flex items-center gap-2.5 text-lg font-bold">
            Two-step sign-in
            <span className={`rounded-full px-2.5 py-0.5 text-[13px] font-semibold ${on ? "bg-emerald-100 text-emerald-900" : "bg-gray-100 text-body"}`}>{on ? "On" : "Off"}</span>
          </h2>
          <p className="mb-4 max-w-[60ch] text-body">
            After your password, Wiseflow asks for a six-digit code from an authenticator app on your phone. Someone who learns your password still cannot sign in.
          </p>
          {error && <p role="alert" className={`${errorBox} mb-4`}>{error}</p>}
          {notice && <p role="status" className={ok}>{notice}</p>}

          {!on && !setup && (
            <button type="button" disabled={busy} className={darkButton} onClick={() => run(async () => setSetup((await twoStepSetup()).data), "Setup could not be started. Try again.")}>
              Set up two-step sign-in
            </button>
          )}

          {setup && (
            <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); run(async () => { await twoStepEnable(code); finish(true, "Two-step sign-in is on. You will be asked for a code the next time you sign in."); }, "That code could not be checked. Try again."); }}>
              <div className="flex flex-wrap items-center gap-5">
                <QrCode value={setup.uri} />
                <ol className="flex min-w-[220px] flex-1 list-decimal flex-col gap-2 pl-5">
                  <li>Open an authenticator app such as Google Authenticator, Microsoft Authenticator or 1Password.</li>
                  <li>Scan this code, or type in the key below.</li>
                  <li>Enter the six digits the app shows for Wiseflow.</li>
                </ol>
              </div>
              <div>
                <span className="text-[13.5px] font-semibold text-body">Key, if you cannot scan</span>
                <code className="block break-all rounded-lg bg-soft px-3 py-2 font-mono text-sm">{setup.secret.replace(/(.{4})/g, "$1 ").trim()}</code>
              </div>
              <label className={`${label} max-w-[220px]`}>
                Six-digit code
                <input required value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric" autoComplete="one-time-code" maxLength={7} className={`${field} font-mono tracking-[0.3em]`} />
              </label>
              <div className="flex flex-wrap gap-2.5">
                <button type="submit" disabled={busy} className={darkButton}>{busy ? "Checking" : "Turn on"}</button>
                <button type="button" className={quiet} onClick={() => { setSetup(null); setCode(""); }}>Cancel</button>
              </div>
            </form>
          )}

          {on && !turningOff && <button type="button" className={quiet} onClick={() => setTurningOff(true)}>Turn off</button>}

          {on && turningOff && (
            <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); run(async () => { await twoStepDisable(password, code); finish(false, "Two-step sign-in is off."); }, "It could not be turned off. Try again."); }}>
              <div className="grid max-w-[520px] gap-4 sm:grid-cols-2">
                <label className={label}>
                  Your password
                  <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" className={field} />
                </label>
                <label className={label}>
                  Six-digit code
                  <input required value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric" autoComplete="one-time-code" maxLength={7} className={`${field} font-mono tracking-[0.3em]`} />
                </label>
              </div>
              <span className={hint}>Lost your phone? An administrator of this Wiseflow server can turn it off for you.</span>
              <div className="flex flex-wrap gap-2.5">
                <button type="submit" disabled={busy} className={darkButton}>{busy ? "Checking" : "Turn off two-step sign-in"}</button>
                <button type="button" className={quiet} onClick={() => { setTurningOff(false); setCode(""); setPassword(""); }}>Cancel</button>
              </div>
            </form>
          )}
        </div>
        <PhoneCode className="hidden h-32 w-auto sm:block" />
      </div>
    </section>
  );
}

/** Owner only: make every other member sign in with Google. */
export function RequireSsoSection({ org, onChange }: { org: Org; onChange: (org: Org) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (org.my_role !== "owner" || org.account_type === "individual") return null;
  const toggle = async () => {
    setError("");
    setBusy(true);
    try {
      onChange((await setRequireSso(!org.require_sso)).data);
    } catch (e) {
      setError(apiError(e, "The setting could not be changed. Try again."));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className={section}>
      <h2 className="text-lg font-bold">Require Google sign-in</h2>
      <p className="mb-4 max-w-[70ch] text-body">
        When this is on, members of {org.name} can only sign in with Google; their passwords are refused. You, as owner, can still use your password, so the organisation can never be locked out.
      </p>
      {error && <p role="alert" className={`${errorBox} mb-4`}>{error}</p>}
      {!org.sso_available && !org.require_sso ? (
        <p className="text-body">Sign in with Google is not set up on this Wiseflow server, so this cannot be switched on yet.</p>
      ) : (
        <button type="button" role="switch" aria-checked={org.require_sso} disabled={busy} onClick={toggle} className="flex items-center gap-3 font-semibold disabled:opacity-60">
          <span className={`flex h-7 w-12 items-center rounded-full p-1 ${org.require_sso ? "bg-brand-600" : "bg-gray-300"}`}>
            <span className={`h-5 w-5 rounded-full bg-white transition-transform ${org.require_sso ? "translate-x-5" : ""}`} />
          </span>
          {org.require_sso ? "On: members must use Google" : "Off: members can use a password"}
        </button>
      )}
    </section>
  );
}
