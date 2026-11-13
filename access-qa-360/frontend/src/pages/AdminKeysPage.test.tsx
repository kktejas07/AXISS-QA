import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../api/admin";
import type { PlatformPage } from "../api/admin";
import { AdminKeysPage } from "./AdminKeysPage";

vi.mock("../api/admin");
vi.mock("../components/Layout", () => ({ Layout: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));

const page = (stripeSet: boolean, check: PlatformPage["groups"][0]["last_check"] = null): PlatformPage => ({
  providers: [{ id: "anthropic", name: "Claude (Anthropic)" }, { id: "openai", name: "ChatGPT (OpenAI)" }],
  groups: [
    {
      id: "email", title: "Email", about: "Sends invitations.", configured: true, last_check: null,
      fields: [
        { key: "SMTP_HOST", label: "Mail server", secret: false, set: true, source: "server", value: "mail.example.com" },
        { key: "SMTP_PASSWORD", label: "Password", secret: true, set: true, source: "server", hint: "ends in pw99" },
      ],
    },
    {
      id: "stripe", title: "Stripe", about: "Takes card payments.", configured: stripeSet, last_check: check,
      fields: [{ key: "STRIPE_SECRET_KEY", label: "Secret key", secret: true, set: stripeSet, source: stripeSet ? "console" : null, hint: stripeSet ? "ends in 4242" : null }],
    },
  ],
});

const show = () => render(<MemoryRouter><AdminKeysPage /></MemoryRouter>);

beforeEach(() => vi.resetAllMocks());

describe("AdminKeysPage", () => {
  it("never puts a saved key in a field, and sends only what was typed", async () => {
    vi.mocked(api.getPlatform).mockResolvedValue({ data: page(false) } as never);
    vi.mocked(api.savePlatform).mockResolvedValue({ data: page(true) } as never);
    show();
    const email = within(await screen.findByRole("region", { name: "Email" }));
    expect(email.getByLabelText("Password")).toHaveValue("");
    expect(email.getByText(/A key is set \(ends in pw99\), from the server's own settings/)).toBeInTheDocument();
    expect(email.getByLabelText("Mail server")).toHaveValue("mail.example.com");
    expect(email.getByRole("button", { name: "Save Email" })).toBeDisabled();           // nothing typed yet

    const stripe = within(screen.getByRole("region", { name: "Stripe" }));
    expect(stripe.getByText("Not set up")).toBeInTheDocument();
    await userEvent.type(stripe.getByLabelText("Secret key"), "sk_live_new");
    await userEvent.click(stripe.getByRole("button", { name: "Save Stripe" }));
    expect(api.savePlatform).toHaveBeenCalledWith({ STRIPE_SECRET_KEY: "sk_live_new" });
    expect(await stripe.findByText("Set, not tested")).toBeInTheDocument();
    expect(stripe.getByLabelText("Secret key")).toHaveValue("");
    expect(stripe.getByRole("status")).toHaveTextContent("Saved. It is in use from now.");
  });

  it("tests a group and says plainly when the key is refused", async () => {
    vi.mocked(api.getPlatform)
      .mockResolvedValueOnce({ data: page(true) } as never)
      .mockResolvedValue({ data: page(true, { ok: false, detail: "Stripe did not accept the key (status 401)", at: "2026-11-14T10:00:00Z" }) } as never);
    vi.mocked(api.testPlatform).mockResolvedValue({ data: { ok: false, detail: "Stripe did not accept the key (status 401)" } } as never);
    show();
    const stripe = within(await screen.findByRole("region", { name: "Stripe" }));
    await userEvent.click(stripe.getByRole("button", { name: "Test Stripe" }));
    expect(api.testPlatform).toHaveBeenCalledWith("stripe");
    expect(await stripe.findByRole("alert")).toHaveTextContent("Stripe did not accept the key (status 401)");
    expect(stripe.getByText("Last test failed")).toBeInTheDocument();
  });

  it("removes a key saved here, so the server's own applies again", async () => {
    vi.mocked(api.getPlatform).mockResolvedValue({ data: page(true) } as never);
    vi.mocked(api.savePlatform).mockResolvedValue({ data: page(false) } as never);
    show();
    const stripe = within(await screen.findByRole("region", { name: "Stripe" }));
    await userEvent.click(stripe.getByRole("button", { name: "Remove Secret key" }));
    expect(api.savePlatform).toHaveBeenCalledWith({ STRIPE_SECRET_KEY: "" });
    expect(await stripe.findByText("Not set up")).toBeInTheDocument();
  });

  it("says so when the page cannot be loaded", async () => {
    vi.mocked(api.getPlatform).mockRejectedValue(new Error("down"));
    show();
    expect(await screen.findByRole("alert")).toHaveTextContent("Platform keys could not be loaded");
  });
});
