import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../api/wise";
import { Wise, WiseDocuments } from "./Wise";

vi.mock("../api/wise");
// The character is tested on its own in WiseBot.test.tsx.
vi.mock("./WiseBot", () => ({ WiseBot: () => null }));

const reply = (answer: string, more = {}) => ({ data: { answer, sources: [], actions: [], used_ai: false, ...more } }) as never;
const open = async (path = "/") => {
  render(<MemoryRouter initialEntries={[path]}><Wise /></MemoryRouter>);
  await userEvent.click(screen.getByRole("button", { name: "Ask Wise, your assistant" }));
};

beforeEach(() => {
  vi.resetAllMocks();
  sessionStorage.clear();
  vi.mocked(api.getWisePrompts).mockResolvedValue({ data: [{ id: "worst", label: "What are my worst findings?", text: "What are the most serious findings?" }] } as never);
});

describe("Wise", () => {
  it("floats closed until asked for, then opens as a dialog that Escape closes", async () => {
    render(<MemoryRouter><Wise /></MemoryRouter>);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Ask Wise, your assistant" }));
    expect(screen.getByRole("dialog", { name: "Wise, your assistant" })).toBeInTheDocument();
    expect(screen.getByLabelText("Your question for Wise")).toHaveFocus();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("answers a typed question and links to where the answer came from", async () => {
    vi.mocked(api.askWise).mockResolvedValue(reply("Fix the search query first.", { sources: [{ title: "Critical: SQL injection", link: "/audits/a1?tab=security", kind: "finding" }] }));
    await open();
    await userEvent.type(screen.getByLabelText("Your question for Wise"), "How do I fix it?{Enter}");
    expect(await screen.findByText("Fix the search query first.")).toBeInTheDocument();
    expect(screen.getByText("How do I fix it?")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Critical: SQL injection" })).toHaveAttribute("href", "/audits/a1?tab=security");
    expect(screen.getByLabelText("Your question for Wise")).toHaveValue("");
  });

  it("starts from a ready-made question", async () => {
    vi.mocked(api.askWise).mockResolvedValue(reply("Two findings are critical."));
    await open();
    await userEvent.click(await screen.findByRole("button", { name: "What are my worst findings?" }));
    await waitFor(() => expect(api.askWise).toHaveBeenCalledWith([{ role: "user", content: "What are the most serious findings?" }], undefined));
    expect(await screen.findByText("Two findings are critical.")).toBeInTheDocument();
  });

  it("offers a link to do what was asked, and never does it itself", async () => {
    vi.mocked(api.askWise).mockResolvedValue(reply("I can take you to the scan screen.", { actions: [{ label: "Start a scan of https://shop.example.com", path: "/scans/new?url=https://shop.example.com" }] }));
    await open();
    await userEvent.type(screen.getByLabelText("Your question for Wise"), "scan https://shop.example.com{Enter}");
    expect(await screen.findByRole("link", { name: /Start a scan of/ })).toHaveAttribute("href", "/scans/new?url=https://shop.example.com");
  });

  it("includes the scan being looked at, and keeps the conversation going", async () => {
    vi.mocked(api.askWise).mockResolvedValue(reply("It is a critical finding."));
    await open("/audits/11111111-2222-3333-4444-555555555555");
    await userEvent.type(screen.getByLabelText("Your question for Wise"), "first{Enter}");
    await screen.findByText("It is a critical finding.");
    await userEvent.type(screen.getByLabelText("Your question for Wise"), "second{Enter}");
    await waitFor(() => expect(api.askWise).toHaveBeenCalledTimes(2));
    const [messages, audit] = vi.mocked(api.askWise).mock.calls[1];
    expect(messages.map((m) => m.content)).toEqual(["first", "It is a critical finding.", "second"]);
    expect(audit).toBe("11111111-2222-3333-4444-555555555555");
  });

  it("says so when it cannot answer, and keeps the question on screen", async () => {
    vi.mocked(api.askWise).mockRejectedValue(new Error("offline"));
    await open();
    await userEvent.type(screen.getByLabelText("Your question for Wise"), "hello?{Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent("Wise could not answer just now");
    expect(screen.getByText("hello?")).toBeInTheDocument();
  });

  it("does not send an empty question", async () => {
    await open();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Your question for Wise"), "   {Enter}");
    expect(api.askWise).not.toHaveBeenCalled();
  });
});

describe("WiseDocuments", () => {
  const doc = { id: "d1", name: "requirements.md", size: 4200, created_at: "2026-11-14T00:00:00Z" };

  it("lets an admin add and remove documents", async () => {
    vi.mocked(api.getWiseDocuments).mockResolvedValueOnce({ data: [] } as never).mockResolvedValue({ data: [doc] } as never);
    vi.mocked(api.addWiseDocument).mockResolvedValue({ data: doc } as never);
    render(<WiseDocuments canEdit />);
    expect(await screen.findByText("No documents yet. Wise answers from your scans only.")).toBeInTheDocument();
    const file = new File(["# Refunds"], "requirements.md", { type: "text/markdown" });
    await userEvent.upload(screen.getByLabelText("Add a document"), file);
    expect(api.addWiseDocument).toHaveBeenCalledWith(file);
    expect(await screen.findByRole("status")).toHaveTextContent("requirements.md added");
    expect(screen.getByRole("button", { name: "Remove requirements.md" })).toBeInTheDocument();
  });

  it("shows members the list without the controls", async () => {
    vi.mocked(api.getWiseDocuments).mockResolvedValue({ data: [doc] } as never);
    render(<WiseDocuments canEdit={false} />);
    expect(await screen.findByText("requirements.md")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Remove/ })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Add a document")).not.toBeInTheDocument();
  });
});
