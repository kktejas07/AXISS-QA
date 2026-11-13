import { ShieldCheck } from "lucide-react";

export const authField = "h-12 w-full rounded-[10px] border border-gray-400 bg-white px-3.5 text-[15px] disabled:bg-soft disabled:text-body";
export const authButton = "h-[52px] rounded-[10px] bg-brand-600 font-bold text-white hover:bg-brand-700 disabled:opacity-60";

/** The card every signed-out page sits in: sign in, forgot password, new password. */
export function AuthCard({ title, intro, children }: { title: string; intro?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-soft p-4 font-sans text-ink">
      <main className="w-full max-w-md rounded-2xl border-2 border-ink bg-white p-8 shadow-hard">
        <div className="mb-6 flex items-center gap-2.5 text-[19px] font-extrabold tracking-tight">
          <span className="flex h-[30px] w-[30px] items-center justify-center rounded-[9px] bg-brand-600 text-white">
            <ShieldCheck className="h-[17px] w-[17px]" strokeWidth={2.4} aria-hidden="true" />
          </span>
          Wiseflow
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
