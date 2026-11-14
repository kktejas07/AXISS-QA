import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Faq } from "./Faq";

const items = [{ q: "What is it?", a: "A testing tool." }, { q: "Is it free?", a: "There is a free plan." }];

describe("Faq", () => {
  it("starts with the first answer open and opens one at a time", async () => {
    render(<Faq items={items} />);
    const [first, second] = screen.getAllByRole("button");
    expect(first).toHaveAttribute("aria-expanded", "true");
    expect(second).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("region", { name: "What is it?" })).toBeVisible();

    await userEvent.click(second);
    expect(first).toHaveAttribute("aria-expanded", "false");
    expect(second).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("region", { name: "Is it free?" })).toHaveTextContent("There is a free plan.");

    await userEvent.click(second);                       // pressing an open question closes it
    expect(second).toHaveAttribute("aria-expanded", "false");
  });

  it("keeps every answer in the page while closed, for search engines and find-in-page", () => {
    const { container } = render(<Faq items={items} />);
    expect(container).toHaveTextContent("There is a free plan.");
    expect(document.getElementById(screen.getAllByRole("button")[1].getAttribute("aria-controls")!)).toHaveStyle({ visibility: "hidden" });
  });
});
