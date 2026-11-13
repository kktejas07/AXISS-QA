import { Link, NavLink, useNavigate } from "react-router-dom";
import { Activity, Building2, CalendarClock, FolderKanban, LayoutDashboard, ListChecks, LogOut, Plus, ScrollText, Settings, Sparkles, Users } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { clearMe, useMe } from "../hooks/useMe";
import type { Permission } from "../types";
import { Logo } from "./Logo";

// `needs` hides an item from roles that cannot use it (viewers cannot start scans).
type NavItem = { to: string; label: string; icon: LucideIcon; end?: boolean; needs?: Permission };

const userNav: NavItem[] = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/scans/new", label: "New scan", icon: Plus, needs: "scan.run" },
  { to: "/audits", label: "Scans", icon: ListChecks },
  { to: "/schedules", label: "Schedules", icon: CalendarClock },
  { to: "/projects", label: "Projects", icon: FolderKanban },
  { to: "/settings", label: "Settings", icon: Settings },
];

const adminNav: NavItem[] = [
  { to: "/admin", label: "Users and platform", icon: Users, end: true },
  { to: "/admin/organizations", label: "Organisations", icon: Building2 },
  { to: "/admin/queue", label: "Scan queue", icon: ListChecks },
  { to: "/admin/ai-usage", label: "AI usage", icon: Sparkles },
  { to: "/admin/health", label: "System health", icon: Activity },
  { to: "/admin/audit-log", label: "Audit log", icon: ScrollText },
];

/**
 * App shell with a side menu. The admin variant is dark so staff can tell at a
 * glance that they are looking at every customer's data, not their own.
 */
export function Layout({ children, variant = "user" }: { children: React.ReactNode; variant?: "user" | "admin" }) {
  const navigate = useNavigate();
  const me = useMe();
  const admin = variant === "admin";
  const nav = (admin ? adminNav : userNav).filter((item) => !item.needs || !me || me.permissions.includes(item.needs));

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
          ? "bg-white text-brand-950 font-bold"
          : "text-brand-100 hover:text-white font-medium"
        : active
          ? "bg-ink text-white font-semibold"
          : "text-body hover:text-ink font-medium",
    ].join(" ");

  const quiet = admin ? "text-brand-100 hover:text-white" : "text-body hover:text-ink";

  return (
    <div className="min-h-screen bg-soft font-sans text-ink md:flex">
      <aside
        className={`shrink-0 md:w-60 md:min-h-screen flex flex-col gap-6 px-3.5 py-5 border-b md:border-b-0 md:border-r ${
          admin ? "bg-brand-950 text-white border-brand-950" : "bg-white border-line"
        }`}
      >
        <div className="flex flex-col gap-2.5 px-2">
          <Link to="/" aria-label="Wiseflow, home">
            <Logo reversed={admin} />
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
          {me && (
            <p className={`px-3 pt-2 text-[13px] ${admin ? "text-brand-300" : "text-body"}`}>
              <span className="block truncate font-semibold">{me.organization.name}</span>
              <span className="block truncate">{me.email}</span>
            </p>
          )}
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
