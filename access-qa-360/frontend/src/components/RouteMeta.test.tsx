import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { RouteMeta } from "./RouteMeta";

const at = (path: string) => render(<MemoryRouter initialEntries={[path]}><RouteMeta /></MemoryRouter>);
const robots = () => document.head.querySelector('meta[name="robots"]')?.getAttribute("content");

afterEach(() => localStorage.clear());

describe("RouteMeta", () => {
  it("gives each public page its own title and description, and lets it be indexed", () => {
    at("/pricing");
    expect(document.title).toBe("Pricing: Wiseflow");
    expect(document.head.querySelector('meta[name="description"]')?.getAttribute("content")).toMatch(/free plan for one person/);
    expect(robots()).toBe("index, follow");
    expect(document.head.querySelector('link[rel="canonical"]')?.getAttribute("href")).toBe(`${location.origin}/pricing`);
  });

  it("keeps the signed-in app and draft legal pages out of search results", () => {
    at("/settings");
    expect(document.title).toBe("Wiseflow");
    expect(robots()).toBe("noindex, nofollow");
    at("/terms");
    expect(robots()).toBe("noindex, nofollow");
  });

  it("treats the home address as the public page only when nobody is signed in", () => {
    at("/");
    expect(robots()).toBe("index, follow");
    localStorage.setItem("token", "t");
    at("/");
    expect(robots()).toBe("noindex, nofollow");
  });
});
