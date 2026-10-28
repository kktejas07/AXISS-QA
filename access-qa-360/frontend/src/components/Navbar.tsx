import { Link, useNavigate } from "react-router-dom";
import { ShieldCheck, LogOut } from "lucide-react";

export function Navbar() {
  const navigate = useNavigate();
  return (
    <nav className="bg-brand-900 text-white px-6 py-3 flex items-center justify-between">
      <Link to="/" className="flex items-center gap-2 font-semibold text-lg">
        <ShieldCheck className="w-6 h-6 text-indigo-400" />
        <span>
          Access QA <span className="text-indigo-400">360</span>
        </span>
      </Link>
      <button
        onClick={() => {
          localStorage.removeItem("token");
          navigate("/login");
        }}
        className="flex items-center gap-1 text-sm text-indigo-300 hover:text-white"
      >
        <LogOut className="w-4 h-4" /> Sign out
      </button>
    </nav>
  );
}
