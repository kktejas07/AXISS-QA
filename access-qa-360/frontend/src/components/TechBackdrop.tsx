import { Bot, Braces, Bug, Cloud, CodeXml, Cpu, Database, FlaskConical, Gauge, GitBranch, Globe, KeyRound, Lock, ScanSearch, ShieldCheck, Smartphone, Terminal, Workflow } from "lucide-react";
import type { LucideIcon } from "lucide-react";

/**
 * Decoration only: the things a tester works with (code, bugs, APIs, devices,
 * locks), scattered behind a section as small tiles that drift slowly.
 * It is hidden from screen readers, never takes a click, and stands still for
 * people who ask for reduced motion. Put it inside a `relative overflow-hidden`
 * box and give the content above it `relative`.
 */
type Spot = { icon: LucideIcon; x: number; y: number; size: number; turn: number; wait: number; phone?: boolean };

// x and y are percentages of the box. The middle is left clear so text stays easy to read.
const layouts: Record<"hero" | "band" | "auth" | "band-light", Spot[]> = {
  // Along the top and the right of a page's opening, clear of its heading.
  "band-light": [
    { icon: ShieldCheck, x: 62, y: 6, size: 40, turn: 7, wait: 0.4 },
    { icon: CodeXml, x: 78, y: 16, size: 46, turn: -8, wait: 1.3, phone: true },
    { icon: Bug, x: 93, y: 7, size: 42, turn: 10, wait: 2.2 },
    { icon: Braces, x: 97, y: 30, size: 40, turn: -6, wait: 0.9 },
    { icon: Bot, x: 86, y: 34, size: 36, turn: 6, wait: 2.8 },
  ],
  hero: [
    { icon: CodeXml, x: 2.5, y: 12, size: 46, turn: -8, wait: 0 },
    { icon: Bug, x: 93, y: 9, size: 44, turn: 10, wait: 1.2, phone: true },
    { icon: ShieldCheck, x: 46, y: 8, size: 40, turn: 6, wait: 2.1 },
    { icon: Terminal, x: 1, y: 68, size: 40, turn: 7, wait: 0.6 },
    { icon: Braces, x: 96, y: 52, size: 42, turn: -6, wait: 1.8 },
    { icon: GitBranch, x: 51, y: 95, size: 38, turn: -10, wait: 2.6 },
    { icon: Smartphone, x: 88, y: 90, size: 40, turn: 8, wait: 0.9, phone: true },
    { icon: Database, x: 7, y: 92, size: 36, turn: -5, wait: 3.1 },
    { icon: Bot, x: 70, y: 7, size: 36, turn: -9, wait: 1.5 },
    { icon: Lock, x: 24, y: 7, size: 34, turn: 9, wait: 2.9 },
    { icon: FlaskConical, x: 68, y: 95, size: 36, turn: 6, wait: 0.3 },
    { icon: Globe, x: 33, y: 95, size: 34, turn: -7, wait: 2.3 },
  ],
  band: [
    { icon: ScanSearch, x: 3, y: 26, size: 44, turn: -8, wait: 0, phone: true },
    { icon: Bug, x: 6.5, y: 82, size: 34, turn: 10, wait: 3.2 },
    { icon: KeyRound, x: 46, y: 86, size: 34, turn: -6, wait: 0.8 },
    { icon: Cpu, x: 60, y: 20, size: 38, turn: 9, wait: 2.2 },
    { icon: Workflow, x: 63, y: 82, size: 36, turn: 7, wait: 1.4 },
    { icon: Cloud, x: 84, y: 15, size: 38, turn: 6, wait: 1.9 },
    { icon: Gauge, x: 96, y: 60, size: 40, turn: -9, wait: 2.7, phone: true },
  ],
  auth: [
    { icon: CodeXml, x: 8, y: 12, size: 52, turn: -8, wait: 0, phone: true },
    { icon: ShieldCheck, x: 86, y: 10, size: 50, turn: 9, wait: 1.1, phone: true },
    { icon: Bug, x: 14, y: 78, size: 48, turn: 8, wait: 2.0, phone: true },
    { icon: Braces, x: 82, y: 80, size: 50, turn: -7, wait: 0.7, phone: true },
    { icon: Terminal, x: 24, y: 44, size: 42, turn: 6, wait: 2.8 },
    { icon: Smartphone, x: 74, y: 46, size: 42, turn: -10, wait: 1.6 },
    { icon: GitBranch, x: 48, y: 4, size: 40, turn: 7, wait: 3.3 },
    { icon: Bot, x: 50, y: 90, size: 40, turn: -6, wait: 0.4 },
    { icon: Database, x: 3, y: 46, size: 40, turn: 10, wait: 2.4 },
    { icon: Lock, x: 94, y: 46, size: 40, turn: -9, wait: 1.3 },
  ],
};

export function TechBackdrop({ variant = "hero" }: { variant?: "hero" | "band" | "auth" | "band-light" }) {
  const dark = variant === "band";
  return (
    <div aria-hidden="true" data-testid="tech-backdrop" className="pointer-events-none absolute inset-0 select-none overflow-hidden">
      {layouts[variant].map(({ icon: Icon, x, y, size, turn, wait, phone }, i) => (
        <span
          key={i}
          className={`wf-drift absolute items-center justify-center rounded-[28%] border ${phone ? "flex" : "hidden md:flex"} ${
            dark ? "border-white/20 bg-white/[0.06] text-white/40" : "border-brand-200 bg-white/70 text-brand-300 shadow-[3px_3px_0_0_rgb(224_231_255)]"
          }`}
          style={{
            left: `${x}%`, top: `${y}%`, width: size, height: size,
            // Each tile keeps its own tilt and starts its drift at a different moment, so they never move in step.
            ["--turn" as string]: `${turn}deg`, animationDelay: `-${wait}s`, animationDuration: `${7 + (i % 4)}s`,
          }}
        >
          <Icon style={{ width: size * 0.5, height: size * 0.5 }} strokeWidth={1.75} />
        </span>
      ))}
    </div>
  );
}
