import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AuditJob } from "../api/audits";
import type { Changes, ScanBrief, Standards } from "../api/insights";
import * as api from "../api/insights";
import * as wiseApi from "../api/wise";
import { ChangesTab, ConversationsTab, EndpointsTab, FlowsTab, SmokeTest, PerformanceTab, StandardsTab, TrendChart } from "./ScanInsights";

vi.mock("../api/insights");
vi.mock("../api/wise");
vi.mock("../hooks/useMe", () => ({ useCan: () => true }));

const brief = (id: string, risk: number | null, date: string): ScanBrief => ({ id, label: "shop.example.com", created_at: date, risk_score: risk, findings: 2, counts: {}, branch: null });
const job = (more: Partial<AuditJob> = {}) => ({ id: "now", label: "shop.example.com", source_type: "web", ...more }) as AuditJob;
const finding = (title: string, severity = "high") => ({ source: "security" as const, index: 0, severity, title, location: "https://shop.example.com/api" });
const ok = <T,>(data: T) => Promise.resolve({ data }) as never;

beforeEach(() => vi.resetAllMocks());

describe("TrendChart", () => {
  it("draws nothing until there are two scores to join", () => {
    const { container } = render(<TrendChart history={[brief("a", 40, "2026-11-01")]} currentId="a" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("describes the scores for people who cannot see the line", () => {
    render(<TrendChart history={[brief("a", 60, "2026-11-01"), brief("b", null, "2026-11-05"), brief("now", 30, "2026-11-08")]} currentId="now" />);
    expect(screen.getByRole("img", { name: "Risk score for the last 2 scans: 60, 30" })).toBeInTheDocument();
  });
});

describe("ChangesTab", () => {
  it("says there is nothing to compare with on a first scan", async () => {
    vi.mocked(api.getChanges).mockReturnValue(ok<Changes>({ scan: brief("now", 30, "2026-11-08"), baseline: null, new: [], fixed: [], unchanged: 0, history: [] }));
    render(<MemoryRouter><ChangesTab job={job()} /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Nothing to compare with yet" })).toBeInTheDocument();
  });

  it("lists what is new and what was fixed, and how the risk score moved", async () => {
    vi.mocked(api.getChanges).mockReturnValue(ok<Changes>({
      scan: brief("now", 30, "2026-11-08"), baseline: brief("old", 60, "2026-11-01"),
      new: [finding("Open CORS policy", "medium")], fixed: [finding("SQL injection", "critical")], unchanged: 4,
      history: [brief("old", 60, "2026-11-01"), brief("now", 30, "2026-11-08")],
    }));
    render(<MemoryRouter><ChangesTab job={job()} /></MemoryRouter>);
    expect(await screen.findByText("Open CORS policy")).toBeInTheDocument();
    expect(screen.getByText("SQL injection")).toBeInTheDocument();
    expect(screen.getByText("30 (down 30)")).toBeInTheDocument();
    expect(api.getChanges).toHaveBeenCalledWith("now", undefined);
  });

  it("explains a failed load instead of spinning for ever", async () => {
    vi.mocked(api.getChanges).mockRejectedValue(new Error("offline"));
    render(<MemoryRouter><ChangesTab job={job()} /></MemoryRouter>);
    expect(await screen.findByRole("alert")).toHaveTextContent("The comparison could not be loaded");
  });
});

describe("StandardsTab", () => {
  const standards: Standards = {
    standard: "OWASP Top 10 (2021)", covered: 1, other: [], accessibility: [],
    categories: [
      { code: "A01", name: "Broken access control", count: 0, worst: null, findings: [] },
      { code: "A03", name: "Injection", count: 1, worst: "critical", findings: [finding("SQL injection", "critical")] },
    ],
  };

  it("opens a category to show its findings and leaves empty ones closed", async () => {
    vi.mocked(api.getStandards).mockReturnValue(ok(standards));
    render(<StandardsTab job={job()} />);
    const injection = await screen.findByRole("button", { name: /A03.*Injection/ });
    expect(screen.getByRole("button", { name: /A01.*Broken access control/ })).toBeDisabled();
    expect(screen.queryByText("SQL injection")).not.toBeInTheDocument();
    await userEvent.click(injection);
    expect(screen.getByText("SQL injection")).toBeInTheDocument();
    expect(injection).toHaveAttribute("aria-expanded", "true");
  });

  it("does not present an empty result as a pass", async () => {
    vi.mocked(api.getStandards).mockReturnValue(ok({ ...standards, covered: 0, categories: standards.categories.map((c) => ({ ...c, count: 0, findings: [], worst: null })) }));
    render(<StandardsTab job={job()} />);
    expect(await screen.findByText(/That is not proof the app meets the standard/)).toBeInTheDocument();
  });
});

describe("PerformanceTab", () => {
  it("marks an average that is over the limit and lists what to fix", () => {
    const performance = {
      pages_measured: 1, note: "Measured once per page from the scan server.",
      averages: { lcp_ms: 5200, fcp_ms: 900, ttfb_ms: 300, bytes: 400000 },
      pages: [{ url: "https://shop.example.com/cart", ttfb_ms: 300, fcp_ms: 900, lcp_ms: 5200, load_ms: 6000, bytes: 400000, requests: 22, dom_nodes: 300 }],
      findings: [{ severity: "medium", title: "Largest contentful paint is poor", description: "It is 5.2 s.", remediation: "Compress the image.", affected_url: "https://shop.example.com/cart" }],
    };
    render(<PerformanceTab job={job({ tier1_result: { performance } })} />);
    expect(screen.getByText("Over the recommended 2.5 s")).toBeInTheDocument();
    expect(screen.getAllByText("Within the recommended 1.8 s")).toHaveLength(1);
    expect(screen.getByText("Largest contentful paint is poor")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "/cart" })).toBeInTheDocument();
  });

  it("says so when no page was timed", () => {
    render(<PerformanceTab job={job({ tier1_result: {} })} />);
    expect(screen.getByRole("heading", { name: "No pages were timed" })).toBeInTheDocument();
  });
});

describe("EndpointsTab", () => {
  it("shows which endpoints need sign-in", () => {
    const apiInfo = { title: "Shop API", version: "2", format: "OpenAPI 3.0.0", operations: 2, secured: 1, endpoints: [
      { method: "GET", path: "/orders/{id}", summary: "Read an order", secured: true },
      { method: "DELETE", path: "/orders/{id}", summary: "", secured: false },
    ] };
    render(<EndpointsTab job={job({ source_type: "api", tier1_result: { api: apiInfo } })} />);
    expect(screen.getByText(/1 of 2 endpoints need sign-in/)).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Not required" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Not described" })).toBeInTheDocument();
  });
});

describe("FlowsTab", () => {
  const node = (id: number, path: string, depth: number, more = {}) => ({ id, path, url: `https://shop.example.com${path}`, title: `Page ${path}`, status: 200, depth, forms: 0, form_fields: [], api_calls: [], a11y: 0, lcp_ms: 900, ...more });

  it("draws each page, and shows the picked page's forms and requests", async () => {
    vi.mocked(wiseApi.getFlows).mockReturnValue(ok({
      nodes: [node(0, "/", 0), node(1, "/cart", 1), node(2, "/checkout", 2, { forms: 1, form_fields: ["card", "expiry"], api_calls: ["POST https://shop.example.com/api/pay"], a11y: 2 })],
      edges: [{ from: 0, to: 1 }, { from: 1, to: 2 }, { from: 1, to: 0 }], pages_crawled: 30, shown: 3,
    }));
    render(<FlowsTab job={job()} />);
    expect(await screen.findByRole("button", { name: "Page /" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText(/The first 3 of 30 pages are shown/)).toBeInTheDocument();
    expect(screen.getByText("No forms on this page")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Page /checkout" }));
    expect(screen.getByRole("heading", { name: "/checkout" })).toBeInTheDocument();
    expect(screen.getByText("card")).toBeInTheDocument();
    expect(screen.getByText("POST https://shop.example.com/api/pay")).toBeInTheDocument();
  });

  it("says so when the scan visited no pages", async () => {
    vi.mocked(wiseApi.getFlows).mockReturnValue(ok({ nodes: [], edges: [], pages_crawled: 0, shown: 0 }));
    render(<FlowsTab job={job()} />);
    expect(await screen.findByRole("heading", { name: "No pages to map" })).toBeInTheDocument();
  });
});

describe("ConversationsTab", () => {
  const probe = (id: string, verdict: "pass" | "fail" | "review", name: string) => ({ id, category: "Prompt injection", name, severity: "high", prompt: `message ${id}`, reply: `reply ${id}`, verdict, why: `why ${id}` });
  const chatbot = { greeting: "Hi", note: "Replies are judged by fixed rules.", passed: 1, failed: 1, review: 1, errors: 0,
    probes: [probe("a", "pass", "Stayed on task"), probe("b", "fail", "Told to ignore its instructions"), probe("c", "review", "Asked about a made-up product")] };

  it("shows what needs attention first, with the message, the reply and the verdict", async () => {
    render(<ConversationsTab job={job({ source_type: "chatbot", tier1_result: { chatbot } })} />);
    expect(screen.getByRole("heading", { name: "Told to ignore its instructions" })).toBeInTheDocument();
    expect(screen.getByText("message b")).toBeInTheDocument();
    expect(screen.getByText("reply b")).toBeInTheDocument();
    expect(screen.getByText("why b")).toBeInTheDocument();
    expect(screen.getByText("Check by hand", { selector: "span" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Stayed on task" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "All (3)" }));
    expect(screen.getByRole("heading", { name: "Stayed on task" })).toBeInTheDocument();
  });

  it("explains when the bot could not be reached", () => {
    render(<ConversationsTab job={job({ source_type: "chatbot", tier1_result: { error: "The chatbot answered with an error (status 401)" } })} />);
    expect(screen.getByText("The chatbot answered with an error (status 401)")).toBeInTheDocument();
  });
});

describe("SmokeTest", () => {
  it("starts a run and says it is in progress", async () => {
    vi.mocked(api.startSmokeRun).mockReturnValue(ok({ state: "running", total: 6 }));
    render(<SmokeTest job={job({ tier1_result: {} })} />);
    await userEvent.click(screen.getByRole("button", { name: "Run a smoke test" }));
    expect(api.startSmokeRun).toHaveBeenCalledWith("now");
    expect(await screen.findByRole("status")).toHaveTextContent("Opening 6 pages");
    expect(screen.getByRole("button", { name: "Running" })).toBeDisabled();
  });

  it("lists each page with what is wrong with it", () => {
    const smoke_run = { state: "done" as const, finished_at: "2026-11-14T00:00:00Z", passed: 1, warned: 0, failed: 1, pages: [
      { url: "https://shop.example.com/", path: "/", status: 200, ms: 800, verdict: "pass" as const, problems: [] },
      { url: "https://shop.example.com/cart", path: "/cart", status: 500, ms: 1200, verdict: "fail" as const, problems: ["The server answered with status 500"] },
    ] };
    render(<SmokeTest job={job({ tier1_result: { smoke_run } })} />);
    expect(screen.getByRole("status")).toHaveTextContent("1 of 2 pages are broken.");
    expect(screen.getByText("The server answered with status 500")).toBeInTheDocument();
    expect(screen.getByText("Broken")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run again" })).toBeEnabled();
  });

  it("shows why a run could not start", async () => {
    vi.mocked(api.startSmokeRun).mockRejectedValue({ response: { data: { detail: "This scan mapped no pages to test" } } });
    render(<SmokeTest job={job({ tier1_result: {} })} />);
    await userEvent.click(screen.getByRole("button", { name: "Run a smoke test" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("This scan mapped no pages to test");
  });
});
