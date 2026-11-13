import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import * as art from "./Illustrations";

const { EmptyPanel, ...pictures } = art;

describe("illustrations", () => {
  it.each(Object.entries(pictures))("%s is a decorative vector hidden from screen readers", (_name, Picture) => {
    const { container } = render(<Picture />);
    const svg = container.querySelector("svg")!;
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg).toHaveAttribute("viewBox", "0 0 240 180");
    expect(svg.querySelectorAll("path, rect, circle").length).toBeGreaterThan(4);
    expect(container.querySelector("image, foreignObject")).toBeNull();   // vectors only, no embedded pictures
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
