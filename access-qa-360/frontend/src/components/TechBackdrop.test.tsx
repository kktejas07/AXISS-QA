import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TechBackdrop } from "./TechBackdrop";

describe("TechBackdrop", () => {
  it("is decoration: hidden from screen readers and never in the way of a click", () => {
    render(<TechBackdrop />);
    const layer = screen.getByTestId("tech-backdrop");
    expect(layer).toHaveAttribute("aria-hidden", "true");
    expect(layer).toHaveClass("pointer-events-none");
    expect(layer.querySelectorAll("svg")).toHaveLength(12);
  });

  it("shows fewer tiles on a phone, so text is never crowded", () => {
    render(<TechBackdrop variant="band" />);
    const tiles = [...screen.getByTestId("tech-backdrop").children];
    expect(tiles).toHaveLength(7);
    expect(tiles.filter((t) => !t.classList.contains("hidden"))).toHaveLength(2);
  });
});
