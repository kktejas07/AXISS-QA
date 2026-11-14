import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { WiseBot } from "./WiseBot";
import type { BotState } from "./WiseBot";

const owl = (state?: BotState) => render(<WiseBot state={state} />).container.querySelector("svg")!;

describe("WiseBot", () => {
  it("is a drawing for decoration, with nothing to fetch", () => {
    const svg = owl();
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg).toHaveAttribute("data-bot", "idle");
    expect(svg.querySelector(".owl-body-breathe")).not.toBeNull();
    expect(svg.querySelector(".owl-blink")).not.toBeNull();
  });

  it("moves differently for what Wise is doing", () => {
    expect(owl("thinking").querySelectorAll(".owl-dot")).toHaveLength(3);
    expect(owl("thinking").querySelector(".owl-look-up")).not.toBeNull();
    expect(owl("searching").querySelector(".owl-look-scan")).not.toBeNull();
    expect(owl("typing").querySelector(".owl-beak-talk")).not.toBeNull();
    expect(owl("working").querySelectorAll(".owl-wings-flap")).toHaveLength(2);
    expect(owl("done").querySelector(".owl-body-hop")).not.toBeNull();
    expect(owl("error").querySelector(".owl-body-shake")).not.toBeNull();
  });

  it("closes its eyes to sleep and to smile", () => {
    expect(owl("sleeping").querySelector(".owl-blink")).toBeNull();
    expect(owl("sleeping").querySelectorAll(".owl-zzz")).toHaveLength(2);
    expect(owl("done").querySelector(".owl-blink")).toBeNull();
  });

  it("has a movement for every state", () => {
    const states: BotState[] = ["idle", "working", "typing", "thinking", "reading", "writing", "designing", "coding", "searching", "listening", "sleeping", "done", "error"];
    for (const s of states) expect(owl(s).getAttribute("data-bot")).toBe(s);
  });
});
