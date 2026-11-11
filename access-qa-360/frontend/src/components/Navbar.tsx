import { Link, useNavigate, useLocation } from "react-router-dom";
import { ShieldCheck, LogOut, Layers, Radar, FolderOpen } from "lucide-react";

export function Navbar() {
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    localStorage.removeItem("token");
    navigate("/login");
  };

  const isActive = (path: string) =>
    location.pathname === path || location.pathname.startsWith(path + "/");

  return (
    <nav className="bg-surface-1 border-b border-surface-3 px-6 py-3 flex items-center justify-between">
      {/* Logo */}
      <Link to="/" className="flex items-center gap-2 font-semibold text-base">
        <div className="bg-accent rounded-badge p-1.5 flex items-center justify-center">
          <ShieldCheck className="w-4 h-4 text-app" />
        </div>
        <span className="text-fg">
          Access QA <span className="text-accent">360</span>
        </span>
      </Link>

      {/* Nav links */}
      <div className="flex items-center gap-1">
        <Link
          to="/"
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-badge text-sm font-medium transition-colors ${
            isActive("/") && location.pathname === "/"
              ? "bg-surface-2 text-fg"
              : "text-muted hover:text-fg hover:bg-surface-2"
          }`}
        >
          Dashboard
        </Link>
        <Link
          to="/scan"
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-badge text-sm font-medium transition-colors ${
            isActive("/scan")
              ? "bg-surface-2 text-fg"
              : "text-muted hover:text-fg hover:bg-surface-2"
          }`}
        >
          <Radar className="w-3.5 h-3.5" />
          New Scan
        </Link>
        <Link
          to="/projects/new"
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-badge text-sm font-medium transition-colors ${
            isActive("/projects")
              ? "bg-surface-2 text-fg"
              : "text-muted hover:text-fg hover:bg-surface-2"
          }`}
        >
          <FolderOpen className="w-3.5 h-3.5" />
          Projects
        </Link>
        <Link
          to="/test-suites"
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-badge text-sm font-medium transition-colors ${
            isActive("/test-suites")
              ? "bg-surface-2 text-fg"
              : "text-muted hover:text-fg hover:bg-surface-2"
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          Test Suites
        </Link>
      </div>

      {/* Logout */}
      <button
        onClick={handleLogout}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-badge text-sm font-medium text-muted hover:text-fg hover:bg-surface-2 transition-colors"
      >
        <LogOut className="w-3.5 h-3.5" />
        Sign out
      </button>
    </nav>
  );
}
