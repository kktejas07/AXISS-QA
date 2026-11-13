import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../api/insights";
import type { Schedule } from "../api/insights";
import { SchedulesPage } from "./SchedulesPage";

vi.mock("../api/insights");
vi.mock("../components/Layout", () => ({ Layout: ({ children }: { children: React.ReactNode }) => <main>{children}</main> }));
const can = vi.hoisted(() => ({ run: true }));
vi.mock("../hooks/useMe", () => ({ useCan: () => can.run, useMe: () => null, clearMe: () => {} }));

const schedule = (more: Partial<Schedule> = {}): Schedule => ({
  id: "s1", source_type: "web", target: "https://shop.example.com", frequency: "weekly", outputs: ["security"], depth: "standard",
  active: true, next_run_at: "2026-11-21T09:00:00Z", last_run_at: null, last_audit_id: null, last_note: null, ...more,
});
const list = (rows: Schedule[]) => vi.mocked(api.getSchedules).mockResolvedValue({ data: rows } as never);
const open = () => render(<MemoryRouter><SchedulesPage /></MemoryRouter>);

beforeEach(() => {
  vi.resetAllMocks();
  can.run = true;
});

describe("SchedulesPage", () => {
  it("invites the first schedule when there are none", async () => {
    list([]);
    open();
    expect(await screen.findByRole("heading", { name: "No scheduled scans yet" })).toBeInTheDocument();
  });

  it("will not add a schedule until permission to test is confirmed", async () => {
    list([]);
    vi.mocked(api.createSchedule).mockResolvedValue({ data: schedule() } as never);
    open();
    await userEvent.click((await screen.findAllByRole("button", { name: "Add a schedule" }))[0]);
    await userEvent.type(screen.getByLabelText("Web address"), "https://shop.example.com");
    const add = screen.getByRole("button", { name: "Add schedule" });
    expect(add).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(add);
    await waitFor(() => expect(api.createSchedule).toHaveBeenCalledWith({
      source_type: "web", target: "https://shop.example.com", frequency: "weekly", outputs: ["security"], depth: "standard", ownership_confirmed: true,
    }));
    expect(await screen.findByRole("status")).toHaveTextContent("Schedule added.");
  });

  it("shows why the last run was skipped", async () => {
    list([schedule({ last_note: "Skipped: All 2 scans for this month are used" })]);
    open();
    expect(await screen.findByText("Skipped: All 2 scans for this month are used")).toBeInTheDocument();
    expect(screen.getByText("shop.example.com")).toBeInTheDocument();
  });

  it("pauses a schedule and says so", async () => {
    list([schedule()]);
    vi.mocked(api.changeSchedule).mockResolvedValue({ data: schedule({ active: false }) } as never);
    open();
    await userEvent.click(await screen.findByRole("button", { name: "Pause" }));
    expect(api.changeSchedule).toHaveBeenCalledWith("s1", { active: false });
    expect(await screen.findByRole("status")).toHaveTextContent("Schedule paused.");
  });

  it("shows the server's reason when a run cannot start", async () => {
    list([schedule()]);
    vi.mocked(api.runScheduleNow).mockRejectedValue({ response: { data: { detail: "All 2 scans for this month are used" } } });
    open();
    await userEvent.click(await screen.findByRole("button", { name: /Run now/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("All 2 scans for this month are used");
  });

  it("gives viewers the list but no controls", async () => {
    can.run = false;
    list([schedule()]);
    open();
    expect(await screen.findByText("shop.example.com")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Pause" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add a schedule" })).not.toBeInTheDocument();
  });
});
