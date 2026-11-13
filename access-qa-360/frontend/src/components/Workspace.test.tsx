import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../api/workspace";
import { FirstStepsCard, NotificationBell } from "./Workspace";

vi.mock("../api/workspace");

const step = (id: string, done: boolean) => ({ id, label: `Step ${id}`, about: "About it.", path: `/${id}`, done });

beforeEach(() => vi.resetAllMocks());

describe("NotificationBell", () => {
  const notices = [
    { id: "scan-2", at: "2026-11-14T10:00:00Z", text: "Scan of Shop finished: 1 critical, 0 high", path: "/audits/2", tone: "bad" as const },
    { id: "scan-1", at: "2026-11-13T10:00:00Z", text: "Scan of Blog finished: 0 critical, 0 high", path: "/audits/1", tone: "ok" as const },
  ];

  it("counts what is new, lists it, and stops counting once it has been opened", async () => {
    vi.mocked(api.getNotifications).mockResolvedValue({ data: notices } as never);
    const { unmount } = render(<MemoryRouter><NotificationBell /></MemoryRouter>);
    await userEvent.click(await screen.findByRole("button", { name: "Notifications, 2 new" }));
    expect(screen.getByRole("link", { name: /Scan of Shop finished/ })).toHaveAttribute("href", "/audits/2");
    expect(screen.getByRole("button", { name: "Notifications" })).toBeInTheDocument();
    unmount();
    render(<MemoryRouter><NotificationBell /></MemoryRouter>);       // a later visit: nothing new since
    expect(await screen.findByRole("button", { name: "Notifications" })).toBeInTheDocument();
  });

  it("says so when nothing has happened", async () => {
    vi.mocked(api.getNotifications).mockResolvedValue({ data: [] } as never);
    render(<MemoryRouter><NotificationBell /></MemoryRouter>);
    await userEvent.click(screen.getByRole("button", { name: "Notifications" }));
    expect(screen.getByText(/Nothing in the last two weeks/)).toBeInTheDocument();
  });
});

describe("FirstStepsCard", () => {
  it("shows progress and can be hidden for good", async () => {
    vi.mocked(api.getFirstSteps).mockResolvedValue({ data: { steps: [step("scan", true), step("schedule", false)], done: 1, total: 2 } } as never);
    const { unmount } = render(<MemoryRouter><FirstStepsCard /></MemoryRouter>);
    expect(await screen.findByText("1 of 2 done")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Step schedule/ })).toHaveAttribute("href", "/schedule");
    await userEvent.click(screen.getByRole("button", { name: "Hide getting started" }));
    expect(screen.queryByText("1 of 2 done")).not.toBeInTheDocument();
    unmount();
    render(<MemoryRouter><FirstStepsCard /></MemoryRouter>);
    expect(screen.queryByRole("region", { name: "Getting started" })).not.toBeInTheDocument();
    expect(api.getFirstSteps).toHaveBeenCalledTimes(1);
  });

  it("goes away once everything is done", async () => {
    vi.mocked(api.getFirstSteps).mockResolvedValue({ data: { steps: [step("scan", true)], done: 1, total: 1 } } as never);
    const { container } = render(<MemoryRouter><FirstStepsCard /></MemoryRouter>);
    await vi.waitFor(() => expect(api.getFirstSteps).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
