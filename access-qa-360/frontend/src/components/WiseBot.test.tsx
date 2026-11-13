import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const player = vi.hoisted(() => ({ loadAnimation: vi.fn(), destroy: vi.fn(), goToAndStop: vi.fn() }));
vi.mock("lottie-web/build/player/lottie_light", () => ({ default: { loadAnimation: player.loadAnimation } }));

const json = (body: unknown, type = "application/json") => Promise.resolve(new Response(JSON.stringify(body), { headers: { "content-type": type } }));
// A fresh copy of the module for each test, because it remembers the files it has fetched.
const load = async () => (await import("./WiseBot")).WiseBot;

beforeEach(() => {
  vi.resetModules();
  player.loadAnimation.mockReset().mockReturnValue({ destroy: player.destroy, goToAndStop: player.goToAndStop });
  player.destroy.mockReset();
  player.goToAndStop.mockReset();
  window.matchMedia = undefined as never;
});

describe("WiseBot", () => {
  it("plays the animation for what Wise is doing, and swaps it when that changes", async () => {
    const fetched = vi.spyOn(globalThis, "fetch").mockImplementation(() => json({ layers: [], w: 200, h: 200 }));
    const WiseBot = await load();
    const { container, rerender } = render(<WiseBot state="searching" />);
    await waitFor(() => expect(player.loadAnimation).toHaveBeenCalledTimes(1));
    expect(fetched.mock.calls[0][0]).toBe("/wise-bot/searching.json");
    expect(player.loadAnimation.mock.calls[0][0]).toMatchObject({ renderer: "svg", loop: true, autoplay: true });
    expect(container.firstElementChild).toHaveAttribute("aria-hidden", "true");

    rerender(<WiseBot state="done" />);
    await waitFor(() => expect(player.loadAnimation).toHaveBeenCalledTimes(2));
    expect(player.destroy).toHaveBeenCalledTimes(1);
    expect(fetched.mock.calls[1][0]).toBe("/wise-bot/done.json");
  });

  it("fetches each file only once", async () => {
    const fetched = vi.spyOn(globalThis, "fetch").mockImplementation(() => json({ layers: [] }));
    const WiseBot = await load();
    const { unmount } = render(<WiseBot state="idle" />);
    await waitFor(() => expect(player.loadAnimation).toHaveBeenCalledTimes(1));
    unmount();
    render(<WiseBot state="idle" />);
    await waitFor(() => expect(player.loadAnimation).toHaveBeenCalledTimes(2));
    expect(fetched).toHaveBeenCalledTimes(1);
  });

  it("shows one still frame to people who ask for reduced motion", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => json({ layers: [] }));
    window.matchMedia = ((q: string) => ({ matches: q.includes("reduce") })) as never;
    const WiseBot = await load();
    render(<WiseBot />);
    await waitFor(() => expect(player.goToAndStop).toHaveBeenCalledWith(40, true));
    expect(player.loadAnimation.mock.calls[0][0]).toMatchObject({ loop: false, autoplay: false });
  });

  it.each([
    ["the file is not installed and the app's own page comes back", () => Promise.resolve(new Response("<!doctype html>", { headers: { "content-type": "text/html" } }))],
    ["the server answers 404", () => Promise.resolve(new Response("", { status: 404 }))],
    ["the network fails", () => Promise.reject(new Error("offline"))],
    ["the file is not an animation", () => json({ hello: "world" })],
  ])("falls back to the drawn owl when %s", async (_name, answer) => {
    vi.spyOn(globalThis, "fetch").mockImplementation(answer as never);
    const WiseBot = await load();
    const { container } = render(<WiseBot />);
    await waitFor(() => expect(container.querySelector("svg[role=presentation]")).not.toBeNull());
    expect(player.loadAnimation).not.toHaveBeenCalled();
  });
});
