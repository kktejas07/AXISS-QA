import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import * as art from "./Illustrations";

// WiseOwl is a square icon rather than a 240 by 180 scene, so it is checked on its own below.
const { EmptyPanel, WiseOwl, ...pictures } = art;

describe("illustrations", () => {
  it.each(Object.entries(pictures))("%s is a decorative vector hidden from screen readers", (_name, Picture) => {
    const { container } = render(<Picture />);
    const svg = container.querySelector("svg")!;
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg).toHaveAttribute("viewBox", "0 0 240 180");
    expect(svg.querySelectorAll("path, rect, circle").length).toBeGreaterThan(4);
    expect(container.querySelector("image, foreignObject")).toBeNull();   // vectors only, no embedded pictures
  });

  it("Wise blinks unless asked to keep still", () => {
    const { container, rerender } = render(<WiseOwl />);
    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    expect(container.querySelectorAll(".wf-blink")).toHaveLength(2);
    rerender(<WiseOwl still />);
    expect(container.querySelectorAll(".wf-blink")).toHaveLength(0);
  });

  it("takes a size from the page that uses it", () => {
    const { container } = render(<art.RadarWindow className="h-20" />);
    expect(container.querySelector("svg")).toHaveClass("h-20");
  });

  it("EmptyPanel pairs the picture with a heading, a sentence and an action", () => {
    render(
      <EmptyPanel art={<art.CalendarClock />} title="No scheduled scans yet" action={<button>Add a schedule</button>}>
        Add a website and it is scanned every week.
      </EmptyPanel>,
    );
    expect(screen.getByRole("heading", { name: "No scheduled scans yet" })).toBeInTheDocument();
    expect(screen.getByText("Add a website and it is scanned every week.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add a schedule" })).toBeInTheDocument();
  });
});
