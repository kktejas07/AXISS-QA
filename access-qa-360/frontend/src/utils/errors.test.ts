import { describe, expect, it } from "vitest";
import { apiError } from "./errors";

describe("apiError", () => {
  it("uses the server's own sentence when it sent one", () => {
    expect(apiError({ response: { data: { detail: "Your organisation has used all 2 scans for this month." } } }, "fallback")).toBe("Your organisation has used all 2 scans for this month.");
  });

  it("reads the first validation message and drops the technical prefix", () => {
    expect(apiError({ response: { data: { detail: [{ msg: "Value error, Enter a full web address" }] } } }, "fallback")).toBe("Enter a full web address");
  });

  it("falls back when the server gave no reason", () => {
    expect(apiError(new Error("Network Error"), "Could not save.")).toBe("Could not save.");
    expect(apiError({ response: { data: { detail: { code: 1 } } } }, "Could not save.")).toBe("Could not save.");
  });
});
