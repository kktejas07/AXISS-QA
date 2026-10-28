import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Layout } from "../components/Layout";
import { createScan } from "../api/scans";
import type { ScanType, ScanProfile, AuthConfig } from "../types";
import { Globe, ChevronDown, ChevronUp, Radar, Loader2 } from "lucide-react";

export function ScanPage() {
  const navigate = useNavigate();
  const [url, setUrl] = useState("");
  const [scanType, setScanType] = useState<ScanType>("passive");
  const [profile, setProfile] = useState<ScanProfile>("owasp-top-10");
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
    setProgress(10);
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
      setProgress(100);
      navigate(`/scans/${data.id}`);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Scan failed to start");
      setScanning(false);
      setProgress(0);
    }
  };

  const scanTypes: { value: ScanType; label: string; desc: string }[] = [
    { value: "passive", label: "Passive", desc: "Read-only, zero writes" },
    { value: "active", label: "Active", desc: "Form submissions, state mutations" },
    { value: "hybrid", label: "Hybrid", desc: "Balanced approach" },
  ];

  const profiles: { value: ScanProfile; label: string }[] = [
    { value: "owasp-top-10", label: "OWASP Top 10" },
    { value: "pci-dss", label: "PCI-DSS" },
    { value: "hipaa", label: "HIPAA" },
    { value: "custom", label: "Custom" },
  ];

  return (
    <Layout>
      <div className="max-w-3xl mx-auto">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-brand-900 flex items-center gap-2">
            <Radar className="w-6 h-6 text-indigo-500" /> New Scan
          </h1>
          <p className="text-gray-500 text-sm mt-1">
            Enter a URL to scan for vulnerabilities, QA gaps, and generate test cases
          </p>
        </div>

        {/* URL Input */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">Target URL</label>
          <div className="flex items-center gap-3">
            <div className="relative flex-1">
              <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com"
                className="w-full pl-11 pr-4 py-3.5 text-lg border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
                disabled={scanning}
              />
            </div>
          </div>
          {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
        </div>

        {/* Scan Type */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">Scan Mode</label>
          <div className="grid grid-cols-3 gap-3">
            {scanTypes.map((t) => (
              <button
                key={t.value}
                onClick={() => setScanType(t.value)}
                disabled={scanning}
                className={`p-3 rounded-lg border text-left transition ${
                  scanType === t.value
                    ? "border-indigo-500 bg-indigo-50 ring-1 ring-indigo-500"
                    : "border-gray-200 hover:border-gray-300"
                }`}
              >
                <p className="font-medium text-sm text-brand-900">{t.label}</p>
                <p className="text-xs text-gray-500 mt-0.5">{t.desc}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Profile */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">Scan Profile</label>
          <select
            value={profile}
            onChange={(e) => setProfile(e.target.value as ScanProfile)}
            disabled={scanning}
            className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none bg-white"
          >
            {profiles.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
        </div>

        {/* Scope */}
        <div className="grid grid-cols-2 gap-4 mb-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Include Paths</label>
            <input
              type="text"
              value={includePaths}
              onChange={(e) => setIncludePaths(e.target.value)}
              placeholder="/api/v2/*, /app/*"
              disabled={scanning}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Exclude Paths</label>
            <input
              type="text"
              value={excludePaths}
              onChange={(e) => setExcludePaths(e.target.value)}
              placeholder="/admin/*, /static/*"
              disabled={scanning}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
            />
          </div>
        </div>

        {/* Crawl Depth & Rate Limit */}
        <div className="grid grid-cols-2 gap-4 mb-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Crawl Depth: <span className="text-indigo-600 font-semibold">{crawlDepth}</span>
            </label>
            <input
              type="range"
              min={1}
              max={5}
              value={crawlDepth}
              onChange={(e) => setCrawlDepth(Number(e.target.value))}
              disabled={scanning}
              className="w-full accent-indigo-600"
            />
            <div className="flex justify-between text-xs text-gray-400 mt-1">
              <span>1</span><span>2</span><span>3</span><span>4</span><span>5</span>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Rate Limit (req/s)</label>
            <input
              type="number"
              min={1}
              max={100}
              value={rateLimit}
              onChange={(e) => setRateLimit(Number(e.target.value))}
              disabled={scanning}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
            />
          </div>
        </div>

        {/* Auth Config */}
        <div className="mb-6 border border-gray-200 rounded-lg">
          <button
            onClick={() => setShowAuth(!showAuth)}
            className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-lg"
          >
            Authentication Configuration
            {showAuth ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
          {showAuth && (
            <div className="px-4 pb-4 space-y-3">
              <select
                value={auth.type}
                onChange={(e) => setAuth({ type: e.target.value as AuthConfig["type"] })}
                disabled={scanning}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white"
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
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                />
              )}
              {auth.type === "cookie" && (
                <input
                  type="text"
                  placeholder="Cookie header value"
                  value={auth.value || ""}
                  onChange={(e) => setAuth({ ...auth, value: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                />
              )}
              {auth.type === "basic" && (
                <div className="grid grid-cols-2 gap-3">
                  <input
                    type="text"
                    placeholder="Username"
                    value={auth.username || ""}
                    onChange={(e) => setAuth({ ...auth, username: e.target.value })}
                    className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  />
                  <input
                    type="password"
                    placeholder="Password"
                    value={auth.password || ""}
                    onChange={(e) => setAuth({ ...auth, password: e.target.value })}
                    className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  />
                </div>
              )}
            </div>
          )}
        </div>

        {/* Progress Bar */}
        {scanning && (
          <div className="mb-6">
            <div className="flex items-center justify-between text-sm mb-2">
              <span className="text-gray-600 flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-indigo-500" />
                Scan in progress...
              </span>
              <span className="text-indigo-600 font-medium">{progress}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2.5">
              <div
                className="bg-indigo-600 h-2.5 rounded-full transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {/* Start Button */}
        <button
          onClick={handleScan}
          disabled={scanning || !url.trim()}
          className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-semibold py-3.5 rounded-xl transition flex items-center justify-center gap-2 text-lg"
        >
          {scanning ? (
            <><Loader2 className="w-5 h-5 animate-spin" /> Scanning...</>
          ) : (
            <><Radar className="w-5 h-5" /> Start Scan</>
          )}
        </button>
      </div>
    </Layout>
  );
}
