import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { AuthCard } from "../components/AuthCard";
import { clearMe } from "../hooks/useMe";

/** Where Google or Microsoft sign-in lands: picks up the session from the address and opens the app. */
export function SsoPage() {
  const navigate = useNavigate();

  useEffect(() => {
    const token = new URLSearchParams(window.location.hash.slice(1)).get("token");
    // Take the token out of the address bar and history straight away.
    window.history.replaceState(null, "", window.location.pathname);
    if (!token) {
      navigate("/login?sso_error=failed", { replace: true });
      return;
    }
    clearMe();
    localStorage.setItem("token", token);
    navigate("/", { replace: true });
  }, [navigate]);

  return (
    <AuthCard title="Signing you in">
      <p className="text-body">One moment.</p>
    </AuthCard>
  );
}
