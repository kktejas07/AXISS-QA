import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Layout } from "../components/Layout";
import { getProjects } from "../api/projects";
import { getScans } from "../api/scans";
import type { Project, Scan } from "../types";
import { FolderOpen, Plus, Radar, Shield, BarChart3, TestTubeDiagonal } from "lucide-react";

export function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [scans, setScans] = useState<Scan[]>([]);

  useEffect(() => {
    getProjects().then((r) => setProjects(r.data)).catch(() => {});
    getScans().then((r) => setScans(r.data)).catch(() => {});
  }, []);

  const totalVulns = scans.reduce((sum, s) => {
    const vc = s.vulnerability_count;
    return sum + (vc ? vc.critical + vc.high + vc.medium + vc.low + vc.informational : 0);
  }, 0);
  const avgCoverage = scans.length > 0
    ? Math.round(scans.reduce((sum, s) => sum + (s.coverage_percent || 0), 0) / scans.length)
    : 0;
  const recentScans = scans.slice(0, 5);

  return (
    <Layout>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-brand-900">Dashboard</h1>
          <p className="text-gray-500 text-sm mt-1">Your QA & Security intelligence at a glance</p>
        </div>
        <div className="flex gap-3">
          <Link
            to="/projects/new"
            className="flex items-center gap-2 bg-white border border-gray-200 hover:border-indigo-300 text-brand-900 text-sm font-semibold px-4 py-2 rounded-lg transition"
          >
            <Plus className="w-4 h-4" /> New Project
          </Link>
          <Link
            to="/scans/new"
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-4 py-2 rounded-lg transition"
          >
            <Radar className="w-4 h-4" /> New Scan
          </Link>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <div className="flex items-center gap-3 mb-2">
            <Radar className="w-5 h-5 text-indigo-500" />
            <span className="text-xs text-gray-500 font-medium">Total Scans</span>
          </div>
          <p className="text-3xl font-bold text-brand-900">{scans.length}</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <div className="flex items-center gap-3 mb-2">
            <Shield className="w-5 h-5 text-red-500" />
            <span className="text-xs text-gray-500 font-medium">Open Vulnerabilities</span>
          </div>
          <p className="text-3xl font-bold text-brand-900">{totalVulns}</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <div className="flex items-center gap-3 mb-2">
            <BarChart3 className="w-5 h-5 text-emerald-500" />
            <span className="text-xs text-gray-500 font-medium">Avg QA Coverage</span>
          </div>
          <p className="text-3xl font-bold text-brand-900">{avgCoverage}%</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <div className="flex items-center gap-3 mb-2">
            <FolderOpen className="w-5 h-5 text-yellow-500" />
            <span className="text-xs text-gray-500 font-medium">Active Projects</span>
          </div>
          <p className="text-3xl font-bold text-brand-900">{projects.length}</p>
        </div>
      </div>

      {/* Recent Scans */}
      <div className="bg-white border border-gray-200 rounded-xl mb-8">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-brand-900">Recent Scans</h2>
          <Link to="/scans/new" className="text-sm text-indigo-600 hover:text-indigo-800 font-medium">View all</Link>
        </div>
        {recentScans.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <Radar className="w-10 h-10 mx-auto mb-3 opacity-40" />
            <p className="font-medium">No scans yet</p>
            <p className="text-sm mt-1">Start your first scan to detect vulnerabilities and QA gaps</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {recentScans.map((s) => {
              const vc = s.vulnerability_count;
              const total = vc ? vc.critical + vc.high + vc.medium + vc.low + vc.informational : 0;
              return (
                <Link key={s.id} to={`/scans/${s.id}`} className="flex items-center gap-4 px-5 py-4 hover:bg-gray-50 transition">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-sm font-bold ${
                    s.risk_grade === "A" ? "bg-emerald-100 text-emerald-700" :
                    s.risk_grade === "B" ? "bg-blue-100 text-blue-700" :
                    s.risk_grade === "C" ? "bg-yellow-100 text-yellow-700" :
                    s.risk_grade === "D" ? "bg-orange-100 text-orange-700" :
                    "bg-red-100 text-red-700"
                  }`}>
                    {s.risk_grade || "?"}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-brand-900 truncate font-mono">{s.url}</p>
                    <p className="text-xs text-gray-500">{new Date(s.created_at).toLocaleString()}</p>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-gray-500">
                    <span>{total} vulns</span>
                    <span>{s.coverage_percent}% covered</span>
                    <span>{s.test_cases_generated} tests</span>
                  </div>
                  <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                    s.status === "completed" ? "bg-emerald-100 text-emerald-700" :
                    s.status === "failed" ? "bg-red-100 text-red-700" :
                    "bg-indigo-100 text-indigo-700 animate-pulse"
                  }`}>
                    {s.status.toUpperCase()}
                  </span>
                </Link>
              );
            })}
          </div>
        )}
      </div>

      {/* Projects Grid */}
      <div className="mb-4">
        <h2 className="font-semibold text-brand-900 mb-4">Projects</h2>
        {projects.length === 0 ? (
          <div className="text-center py-12 text-gray-400 bg-white border border-gray-200 rounded-xl">
            <FolderOpen className="w-10 h-10 mx-auto mb-3 opacity-40" />
            <p className="font-medium">No projects yet</p>
            <p className="text-sm mt-1">Create your first project to start generating tests</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((p) => (
              <Link
                key={p.id}
                to={`/projects/${p.id}/suites`}
                className="bg-white border border-gray-200 rounded-xl p-5 hover:border-indigo-300 hover:shadow-sm transition group"
              >
                <div className="flex items-start justify-between mb-3">
                  <TestTubeDiagonal className="w-5 h-5 text-indigo-500" />
                  <span className="text-xs font-mono text-gray-400">
                    {new Date(p.created_at).toLocaleDateString()}
                  </span>
                </div>
                <h3 className="font-semibold text-brand-900 group-hover:text-indigo-600 transition">{p.name}</h3>
                <p className="text-xs text-gray-500 mt-1 truncate">{p.base_url}</p>
                {p.description && <p className="text-sm text-gray-600 mt-2 line-clamp-2">{p.description}</p>}
              </Link>
            ))}
          </div>
        )}
      </div>
    </Layout>
  );
}
