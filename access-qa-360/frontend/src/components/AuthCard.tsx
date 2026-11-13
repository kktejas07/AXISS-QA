import { TechBackdrop } from "./TechBackdrop";
import { Logo } from "./Logo";

export const authField = "h-12 w-full rounded-[10px] border border-gray-400 bg-white px-3.5 text-[15px] disabled:bg-soft disabled:text-body";
export const authButton = "h-[52px] rounded-[10px] bg-brand-600 font-bold text-white hover:bg-brand-700 disabled:opacity-60";

/** The card every signed-out page sits in: sign in, forgot password, new password. */
export function AuthCard({ title, intro, children }: { title: string; intro?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-soft p-4 font-sans text-ink">
      <TechBackdrop variant="auth" />
      <main className="relative w-full max-w-md rounded-2xl border-2 border-ink bg-white p-8 shadow-hard">
        <div className="mb-6">
          <Logo />
        </div>
        <h1 className="text-2xl font-extrabold tracking-tight">{title}</h1>
        {intro && <p className="mt-1 text-body">{intro}</p>}
        <div className="mt-6">{children}</div>
      </main>
    </div>
  );
}

export function AuthAlert({ children, tone = "error" }: { children: React.ReactNode; tone?: "error" | "ok" | "info" }) {
  const look = { error: "border-red-200 bg-red-50 text-red-800", ok: "border-emerald-200 bg-emerald-50 text-emerald-900", info: "border-gray-300 bg-soft text-ink" }[tone];
  return (
    <p role={tone === "error" ? "alert" : "status"} className={`mb-4 rounded-[10px] border px-4 py-3 ${look}`}>
      {children}
    </p>
  );
}
