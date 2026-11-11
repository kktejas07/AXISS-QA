import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { login } from "../api/auth";
import { ShieldCheck } from "lucide-react";

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const res = await login(email, password);
      localStorage.setItem("token", res.data.access_token);
      navigate("/");
    } catch {
      setError("Invalid email or password");
    }
  };

  return (
    <div className="min-h-screen bg-app flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo mark */}
        <div className="flex items-center gap-2 mb-10 justify-center">
          <div className="bg-accent rounded-badge p-2">
            <ShieldCheck className="w-5 h-5 text-app" />
          </div>
          <span className="text-fg font-semibold text-lg">
            Access QA <span className="text-accent">360</span>
          </span>
        </div>

        <div className="bg-surface-1 border border-surface-3 rounded-card p-8">
          <h1 className="text-xl font-semibold text-fg mb-1">Sign in</h1>
          <p className="text-muted text-sm mb-6">Enter your credentials to continue</p>

          {error && (
            <div className="bg-red-900/20 border border-red-800/40 text-red-400 text-sm rounded-badge px-4 py-2.5 mb-5">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="refero-label">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="you@company.com"
                className="refero-input"
              />
            </div>
            <div>
              <label className="refero-label">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="••••••••"
                className="refero-input"
              />
            </div>
            <button
              type="submit"
              className="refero-btn-primary w-full py-2.5 mt-2"
            >
              Sign in
            </button>
          </form>

          <p className="mt-5 text-center text-sm text-muted">
            No account?{" "}
            <Link to="/register" className="text-accent font-medium hover:text-accent-dim">
              Register
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
