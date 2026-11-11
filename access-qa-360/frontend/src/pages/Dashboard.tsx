import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Layout } from "../components/Layout";
import { getScans } from "../api/scans";
import { getProjects } from "../api/projects";
import type { Scan, Project } from "../types";
import {
  Radar,
  ShieldAlert,
  CheckCircle2,
  FolderOpen,
  Plus,
  ArrowRight,
  TrendingUp,
} from "lucide-react";

function RiskGrade({ grade }: { grade: string }) {
  const map: Record<string, string> = {
    A: "text-emerald-400 bg-emerald-900/30 border-emerald-800/50",
    B: "text-accent bg-accent/15 border-accent/30",
    C: "text-yellow-400 bg-yellow-900/30 border-yellow-800/50",
    D: "text-orange-400 bg-orange-900/30 border-orange-800/50",
    F: "text-red-400 bg-red-900/30 border-red-800/50",
  };
  const cls = map[grade] ?? "text-muted bg-surface-2 border-surface-3";
  return (
    <span className={`inline-flex items-center justify-center w-7 h-7 rounded-badge border text-xs font-bold ${cls}`}>
      {grade}
    </span>
  );
}

export function Dashboard() {
  const [scans, setScans] = useState<Scan[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);

  useEffect(() => {
    getScans().then((r) => setScans(r.data.slice(0, 8)));
    getProjects().then((r) => setProjects(r.data.slice(0, 6)));
  }, []);

  const totalVulns = scans.reduce((s, sc) => s + (sc.vulnerabilities_count ?? 0), 0);
  const criticalCount = scans.reduce((s, sc) => s + (sc.critical_count ?? 0), 0);
  const passedScans = scans.filter((s) => s.risk_grade === "A" || s.risk_grade === "B").length;

  const stats = [
    {
      label: "Total Scans",
      value: scans.length,
      icon: Radar,
      iconColor: "text-accent",
      iconBg: "bg-accent/10",
    },
    {
      label: "Vulnerabilities",
      value: totalVulns,
      icon: ShieldAlert,
      iconColor: "text-red-400",
      iconBg: "bg-red-900/20",
    },
    {
      label: "Critical Issues",
      value: criticalCount,
      icon: TrendingUp,
      iconColor: "text-orange-400",
      iconBg: "bg-orange-900/20",
    },
    {
      label: "Clean Scans",
      value: passedScans,
      icon: CheckCircle2,
      iconColor: "text-emerald-400",
      iconBg: "bg-emerald-900/20",
    },
  ];

  return (
    <Layout>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-fg">Dashboard</h1>
          <p className="text-muted text-sm mt-0.5">Monitor your security and QA posture</p>
        </div>
        <Link
          to="/scan"
          className="refero-btn-primary flex items-center gap-2 px-4 py-2.5 text-sm"
        >
          <Radar className="w-4 h-4" />
          New Scan
        </Link>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="bg-surface-1 border border-surface-3 rounded-card p-5"
          >
            <div className={`inline-flex items-center justify-center w-9 h-9 rounded-badge ${stat.iconBg} mb-3`}>
              <stat.icon className={`w-4.5 h-4.5 ${stat.iconColor}`} />
            </div>
            <p className="text-2xl font-bold text-fg">{stat.value}</p>
            <p className="text-xs text-muted mt-0.5">{stat.label}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Recent scans */}
        <div className="lg:col-span-2 bg-surface-1 border border-surface-3 rounded-card">
          <div className="flex items-center justify-between px-5 py-4 border-b border-surface-3">
            <h2 className="text-sm font-semibold text-fg">Recent Scans</h2>
            <Link
              to="/scan"
              className="flex items-center gap-1 text-xs text-muted hover:text-accent transition-colors"
            >
              New scan <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          {scans.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-14 text-muted">
              <Radar className="w-8 h-8 mb-3 opacity-30" />
              <p className="text-sm font-medium text-fg-soft">No scans yet</p>
              <p className="text-xs mt-1">Run your first scan to see results here</p>
            </div>
          ) : (
            <div className="divide-y divide-surface-3">
              {scans.map((scan) => (
                <Link
                  key={scan.id}
                  to={`/scans/${scan.id}`}
                  className="flex items-center gap-4 px-5 py-3.5 hover:bg-surface-2 transition-colors"
                >
                  {scan.risk_grade && <RiskGrade grade={scan.risk_grade} />}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-fg truncate">{scan.url}</p>
                    <p className="text-xs text-muted mt-0.5">
                      {new Date(scan.created_at).toLocaleDateString()} ·{" "}
                      {scan.vulnerabilities_count ?? 0} findings
                    </p>
                  </div>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-badge font-medium border ${
                      scan.status === "completed"
                        ? "bg-emerald-900/20 text-emerald-400 border-emerald-800/40"
                        : scan.status === "running"
                        ? "bg-accent/15 text-accent border-accent/30"
                        : scan.status === "failed"
                        ? "bg-red-900/20 text-red-400 border-red-800/40"
                        : "bg-surface-2 text-muted border-surface-3"
                    }`}
                  >
                    {scan.status}
                  </span>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Projects */}
        <div className="bg-surface-1 border border-surface-3 rounded-card">
          <div className="flex items-center justify-between px-5 py-4 border-b border-surface-3">
            <h2 className="text-sm font-semibold text-fg">Projects</h2>
            <Link
              to="/projects/new"
              className="flex items-center gap-1 text-xs text-muted hover:text-accent transition-colors"
            >
              <Plus className="w-3 h-3" /> New
            </Link>
          </div>
          {projects.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-14 text-muted">
              <FolderOpen className="w-8 h-8 mb-3 opacity-30" />
              <p className="text-sm font-medium text-fg-soft">No projects</p>
              <p className="text-xs mt-1">Create a project to group scans</p>
            </div>
          ) : (
            <div className="divide-y divide-surface-3">
              {projects.map((project) => (
                <div
                  key={project.id}
                  className="flex items-center gap-3 px-5 py-3.5 hover:bg-surface-2 transition-colors"
                >
                  <div className="w-8 h-8 rounded-badge bg-surface-2 border border-surface-3 flex items-center justify-center shrink-0">
                    <FolderOpen className="w-3.5 h-3.5 text-muted" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-fg truncate">{project.name}</p>
                    <p className="text-xs text-muted truncate font-mono">{project.base_url}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
