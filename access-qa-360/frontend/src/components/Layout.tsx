import { Link, NavLink, useNavigate } from "react-router-dom";
import { FolderPlus, LayoutDashboard, ListChecks, LogOut, Plus, ShieldCheck, Users } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { clearMe, useMe } from "../hooks/useMe";

type NavItem = { to: string; label: string; icon: LucideIcon; end?: boolean };

const userNav: NavItem[] = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/scans/new", label: "New scan", icon: Plus },
  { to: "/audits", label: "Scans", icon: ListChecks },
  { to: "/projects/new", label: "New project", icon: FolderPlus },
];

const adminNav: NavItem[] = [{ to: "/admin", label: "Users and platform", icon: Users, end: true }];

/**
 * App shell with a side menu. The admin variant is dark so staff can tell at a
 * glance that they are looking at every customer's data, not their own.
 */
export function Layout({ children, variant = "user" }: { children: React.ReactNode; variant?: "user" | "admin" }) {
  const navigate = useNavigate();
  const me = useMe();
  const admin = variant === "admin";
  const nav = admin ? adminNav : userNav;

  const signOut = () => {
    localStorage.removeItem("token");
    clearMe();
    navigate("/login");
  };

  const item = (active: boolean) =>
    [
      "flex items-center gap-3 min-h-[44px] px-3 rounded-[10px] text-[15px] no-underline",
      admin
        ? active
          ? "bg-white text-ink font-bold"
          : "text-gray-300 hover:text-white font-medium"
        : active
          ? "bg-ink text-white font-semibold"
          : "text-body hover:text-ink font-medium",
    ].join(" ");

  const quiet = admin ? "text-gray-300 hover:text-white" : "text-body hover:text-ink";

  return (
    <div className="min-h-screen bg-soft font-sans text-ink md:flex">
      <aside
        className={`shrink-0 md:w-60 md:min-h-screen flex flex-col gap-6 px-3.5 py-5 border-b md:border-b-0 md:border-r ${
          admin ? "bg-ink text-white border-ink" : "bg-white border-line"
        }`}
      >
        <div className="flex flex-col gap-2.5 px-2">
          <Link to="/" className="flex items-center gap-2.5 text-[19px] font-extrabold tracking-tight">
            <span className="w-[30px] h-[30px] rounded-[9px] bg-brand-600 text-white flex items-center justify-center">
              <ShieldCheck className="w-[17px] h-[17px]" strokeWidth={2.4} aria-hidden="true" />
            </span>
            Wiseflow
          </Link>
          {admin && (
            <span className="self-start text-xs font-bold text-ink bg-amber-400 rounded-md px-2 py-0.5">Super admin</span>
          )}
        </div>

        <nav aria-label={admin ? "Admin" : "App"} className="flex flex-col gap-0.5">
          {nav.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => item(isActive)}>
              <Icon className="w-[18px] h-[18px]" aria-hidden="true" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="md:mt-auto flex flex-col gap-1">
          {admin ? (
            <Link to="/" className={`flex items-center gap-3 min-h-[44px] px-3 text-[15px] font-medium ${quiet}`}>
              <LayoutDashboard className="w-[18px] h-[18px]" aria-hidden="true" /> Switch to user view
            </Link>
          ) : (
            me?.role === "super_admin" && (
              <Link to="/admin" className={`flex items-center gap-3 min-h-[44px] px-3 text-[15px] font-medium ${quiet}`}>
                <Users className="w-[18px] h-[18px]" aria-hidden="true" /> Admin console
              </Link>
            )
          )}
          {me && <p className={`px-3 pt-2 text-[13px] truncate ${admin ? "text-gray-400" : "text-body"}`}>{me.email}</p>}
          <button
            type="button"
            onClick={signOut}
            className={`flex items-center gap-3 min-h-[44px] px-3 text-[15px] font-medium text-left ${quiet}`}
          >
            <LogOut className="w-[18px] h-[18px]" aria-hidden="true" /> Sign out
          </button>
        </div>
      </aside>

      <main className="flex-1 min-w-0 px-4 py-8 md:px-12">
        <div className="max-w-6xl">{children}</div>
      </main>
    </div>
  );
}
