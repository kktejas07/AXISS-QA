import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../api/insights";
import type { AiSettings } from "../api/insights";
import { AiSettingsSection } from "./AiSettings";

vi.mock("../api/insights");

const providers = [
  { id: "anthropic", name: "Claude (Anthropic)", fast: "claude-haiku-4-5", best: "claude-sonnet-4-5" },
  { id: "openai", name: "ChatGPT (OpenAI)", fast: "gpt-4o-mini", best: "gpt-4o" },
  { id: "custom", name: "Another OpenAI-compatible API", fast: null, best: null },
];
const settings = (more: Partial<AiSettings> = {}): AiSettings => ({ quality: "balanced", own_key: false, key_ending: null, provider: "anthropic", model: null, base_url: null, providers, ...more });

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.getAiSettings).mockResolvedValue({ data: settings() } as never);
});

describe("AiSettingsSection", () => {
  it("saves another provider with its key and an exact model", async () => {
    vi.mocked(api.saveAiSettings).mockResolvedValue({ data: settings({ provider: "openai", own_key: true, key_ending: "WXYZ", model: "gpt-4.1" }) } as never);
    render(<AiSettingsSection canEdit />);
    await userEvent.selectOptions(await screen.findByLabelText(/^Provider/), "openai");
    expect(screen.getByLabelText(/^Your API key/)).toBeRequired();                       // another provider cannot use Wiseflow's key
    expect(screen.getByText(/Leave empty to use gpt-4o-mini and gpt-4o/)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/^Your API key/), "sk-proj-0123456789WXYZ");
    await userEvent.type(screen.getByLabelText(/^Model name/), "gpt-4.1");
    await userEvent.click(screen.getByRole("button", { name: "Save AI settings" }));
    await waitFor(() => expect(api.saveAiSettings).toHaveBeenCalledWith({ quality: "balanced", provider: "openai", model: "gpt-4.1", base_url: undefined, api_key: "sk-proj-0123456789WXYZ" }));
    expect(await screen.findByRole("status")).toHaveTextContent("AI settings saved.");
    expect(screen.getByLabelText(/^Your API key/)).toHaveAttribute("placeholder", "Saved key ending WXYZ");
  });

  it("asks for an address and a model for a custom API", async () => {
    render(<AiSettingsSection canEdit />);
    await userEvent.selectOptions(await screen.findByLabelText(/^Provider/), "custom");
    expect(screen.getByLabelText(/^API address/)).toBeRequired();
    expect(screen.getByLabelText(/^Model name/)).toBeRequired();
  });

  it("shows the provider's reason when the key is refused, and can go back to Wiseflow's own key", async () => {
    vi.mocked(api.getAiSettings).mockResolvedValue({ data: settings({ provider: "openai", own_key: true, key_ending: "WXYZ" }) } as never);
    vi.mocked(api.saveAiSettings).mockRejectedValueOnce({ response: { data: { detail: "The AI provider did not accept the key. Check the key and the model name." } } })
      .mockResolvedValue({ data: settings() } as never);
    render(<AiSettingsSection canEdit />);
    await userEvent.click(await screen.findByRole("button", { name: "Save AI settings" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("did not accept the key");
    await userEvent.click(screen.getByRole("button", { name: "Remove my key" }));
    await waitFor(() => expect(api.saveAiSettings).toHaveBeenLastCalledWith({ quality: "balanced", provider: "anthropic", api_key: "" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Claude are used again");
  });

  it("tells members which provider is in use without letting them change it", async () => {
    vi.mocked(api.getAiSettings).mockResolvedValue({ data: settings({ provider: "openai", own_key: true, key_ending: "WXYZ" }) } as never);
    render(<AiSettingsSection canEdit={false} />);
    expect(await screen.findByText(/Using ChatGPT \(OpenAI\) with your organisation's own key/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save AI settings" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/API key/)).not.toBeInTheDocument();
  });
});
