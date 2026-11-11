import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Layout } from "../components/Layout";
import { createScan } from "../api/scans";
import type { ScanType, ScanProfile, AuthConfig } from "../types";
import { Globe, ChevronDown, ChevronUp, Radar, Loader2, Lock } from "lucide-react";

export function ScanPage() {
  const navigate = useNavigate();
  const [url, setUrl] = useState("");
  const [scanType, setScanType] = useState<ScanType>("passive");
  const [profile, setProfile] = useState<ScanProfile>("owasp_top10");
  const [showAuth, setShowAuth] = useState(false);
  const [auth, setAuth] = useState<AuthConfig>({ type: "none" });
  const [includePaths, setIncludePaths] = useState("");
  const [excludePaths, setExcludePaths] = useState("");
  const [crawlDepth, setCrawlDepth] = useState(3);
  const [rateLimit, setRateLimit] = useState(10);
  const [scanning, setScanning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");

  const handleScan = async () => {
    if (!url.trim()) { setError("URL is required"); return; }
    setError("");
    setScanning(true);
    setProgress(5);
    try {
      const { data } = await createScan({
        url: url.trim(),
        scan_type: scanType,
        profile,
        auth,
        include_paths: includePaths ? includePaths.split(",").map(s => s.trim()) : [],
        exclude_paths: excludePaths ? excludePaths.split(",").map(s => s.trim()) : [],
        crawl_depth: crawlDepth,
        rate_limit: rateLimit,
      });

      const scanId = data.id;
      const apiBase = import.meta.env.VITE_API_URL || "";
      const token = localStorage.getItem("access_token");
      const evtSource = new EventSource(
        `${apiBase}/api/v1/scans/${scanId}/stream?token=${encodeURIComponent(token || "")}`
      );

      evtSource.addEventListener("progress", (e) => {
        try {
          const payload = JSON.parse(e.data);
          setProgress(payload.progress ?? 0);
        } catch {}
      });

      evtSource.addEventListener("done", () => {
        evtSource.close();
        setProgress(100);
        navigate(`/scans/${scanId}`);
      });

      evtSource.addEventListener("error", () => {
        evtSource.close();
        navigate(`/scans/${scanId}`);
      });

    } catch (err: any) {
      setError(err.response?.data?.detail || "Scan failed to start");
      setScanning(false);
      setProgress(0);
    }
  };

  const scanTypes: { value: ScanType; label: string; desc: string }[] = [
    { value: "passive", label: "Passive", desc: "Read-only, zero writes" },
    { value: "active", label: "Active", desc: "Form submissions & mutations" },
    { value: "hybrid", label: "Hybrid", desc: "Balanced approach" },
  ];

  const profiles: { value: ScanProfile; label: string }[] = [
    { value: "owasp_top10", label: "OWASP Top 10" },
    { value: "pci_dss", label: "PCI-DSS" },
    { value: "hipaa", label: "HIPAA" },
    { value: "custom", label: "Custom" },
  ];

  return (
    <Layout>
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-1">
            <Radar className="w-5 h-5 text-accent" />
            <h1 className="text-2xl font-semibold text-fg">New Scan</h1>
          </div>
          <p className="text-muted text-sm">
            Paste a URL to scan for vulnerabilities, QA gaps, and auto-generate test cases
          </p>
        </div>

        {/* URL Input */}
        <div className="mb-5">
          <label className="refero-label">Target URL</label>
          <div className="relative">
            <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-dim" />
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com"
              className="refero-input pl-10 py-3 text-base"
              disabled={scanning}
            />
          </div>
          {error && <p className="text-red-400 text-xs mt-2">{error}</p>}
        </div>

        {/* Scan Type */}
        <div className="mb-5">
          <label className="refero-label">Scan Mode</label>
          <div className="grid grid-cols-3 gap-2">
            {scanTypes.map((t) => (
              <button
                key={t.value}
                onClick={() => setScanType(t.value)}
                disabled={scanning}
                className={`p-3 rounded-card border text-left transition-colors ${
                  scanType === t.value
                    ? "border-accent bg-accent/10 text-fg"
                    : "border-surface-3 bg-surface-1 hover:bg-surface-2 text-fg"
                }`}
              >
                <p className="font-semibold text-sm">{t.label}</p>
                <p className="text-xs text-muted mt-0.5">{t.desc}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Profile */}
        <div className="mb-5">
          <label className="refero-label">Scan Profile</label>
          <select
            value={profile}
            onChange={(e) => setProfile(e.target.value as ScanProfile)}
            disabled={scanning}
            className="refero-input"
          >
            {profiles.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
        </div>

        {/* Scope */}
        <div className="grid grid-cols-2 gap-3 mb-5">
          <div>
            <label className="refero-label">Include Paths</label>
            <input
              type="text"
              value={includePaths}
              onChange={(e) => setIncludePaths(e.target.value)}
              placeholder="/api/v2/*, /app/*"
              disabled={scanning}
              className="refero-input"
            />
          </div>
          <div>
            <label className="refero-label">Exclude Paths</label>
            <input
              type="text"
              value={excludePaths}
              onChange={(e) => setExcludePaths(e.target.value)}
              placeholder="/admin/*, /static/*"
              disabled={scanning}
              className="refero-input"
            />
          </div>
        </div>

        {/* Crawl Depth & Rate Limit */}
        <div className="grid grid-cols-2 gap-3 mb-5">
          <div>
            <label className="refero-label">
              Crawl Depth: <span className="text-accent normal-case font-bold">{crawlDepth}</span>
            </label>
            <input
              type="range"
              min={1}
              max={5}
              value={crawlDepth}
              onChange={(e) => setCrawlDepth(Number(e.target.value))}
              disabled={scanning}
              className="w-full mt-2"
            />
            <div className="flex justify-between text-xs text-muted-dim mt-1">
              <span>1</span><span>2</span><span>3</span><span>4</span><span>5</span>
            </div>
          </div>
          <div>
            <label className="refero-label">Rate Limit (req/s)</label>
            <input
              type="number"
              min={1}
              max={100}
              value={rateLimit}
              onChange={(e) => setRateLimit(Number(e.target.value))}
              disabled={scanning}
              className="refero-input"
            />
          </div>
        </div>

        {/* Auth Config */}
        <div className="mb-6 bg-surface-1 border border-surface-3 rounded-card overflow-hidden">
          <button
            onClick={() => setShowAuth(!showAuth)}
            className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-fg hover:bg-surface-2 transition-colors"
          >
            <span className="flex items-center gap-2 text-muted">
              <Lock className="w-3.5 h-3.5" />
              Authentication Configuration
            </span>
            {showAuth ? (
              <ChevronUp className="w-4 h-4 text-muted-dim" />
            ) : (
              <ChevronDown className="w-4 h-4 text-muted-dim" />
            )}
          </button>
          {showAuth && (
            <div className="px-4 pb-4 space-y-3 border-t border-surface-3 pt-4">
              <select
                value={auth.type}
                onChange={(e) => setAuth({ type: e.target.value as AuthConfig["type"] })}
                disabled={scanning}
                className="refero-input"
              >
                <option value="none">No Authentication</option>
                <option value="cookie">Cookie-based</option>
                <option value="bearer">Bearer Token</option>
                <option value="oauth">OAuth 2.0</option>
                <option value="basic">Basic Auth</option>
              </select>
              {auth.type === "bearer" && (
                <input
                  type="text"
                  placeholder="Bearer token value"
                  value={auth.value || ""}
                  onChange={(e) => setAuth({ ...auth, value: e.target.value })}
                  className="refero-input"
                />
              )}
              {auth.type === "cookie" && (
                <input
                  type="text"
                  placeholder="Cookie header value"
                  value={auth.value || ""}
                  onChange={(e) => setAuth({ ...auth, value: e.target.value })}
                  className="refero-input"
                />
              )}
              {auth.type === "basic" && (
                <div className="grid grid-cols-2 gap-3">
                  <input
                    type="text"
                    placeholder="Username"
                    value={auth.username || ""}
                    onChange={(e) => setAuth({ ...auth, username: e.target.value })}
                    className="refero-input"
                  />
                  <input
                    type="password"
                    placeholder="Password"
                    value={auth.password || ""}
                    onChange={(e) => setAuth({ ...auth, password: e.target.value })}
                    className="refero-input"
                  />
                </div>
              )}
            </div>
          )}
        </div>

        {/* Progress Bar */}
        {scanning && (
          <div className="mb-6">
            <div className="flex items-center justify-between text-xs mb-2">
              <span className="text-muted flex items-center gap-2">
                <Loader2 className="w-3.5 h-3.5 animate-spin text-accent" />
                Scanning in progress…
              </span>
              <span className="text-accent font-semibold">{progress}%</span>
            </div>
            <div className="w-full bg-surface-2 rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-accent h-1.5 rounded-full transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {/* Start Button */}
        <button
          onClick={handleScan}
          disabled={scanning || !url.trim()}
          className="refero-btn-primary w-full py-3.5 flex items-center justify-center gap-2 text-base"
        >
          {scanning ? (
            <><Loader2 className="w-4 h-4 animate-spin" /> Scanning…</>
          ) : (
            <><Radar className="w-4 h-4" /> Start Scan</>
          )}
        </button>
      </div>
    </Layout>
  );
}
