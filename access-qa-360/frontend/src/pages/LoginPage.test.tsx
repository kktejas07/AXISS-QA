import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as auth from "../api/auth";
import { LoginPage } from "./LoginPage";

vi.mock("../api/auth");

const refuse = (status: number, detail: string) => Promise.reject({ response: { status, data: { detail } } });

function open(path = "/login") {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<h1>Overview</h1>} />
      </Routes>
    </MemoryRouter>,
  );
}

async function fill(email = "qa@acme.io", password = "correct-horse") {
  await userEvent.type(screen.getByLabelText("Email"), email);
  await userEvent.type(screen.getByLabelText("Password"), password);
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(auth.getSsoProviders).mockResolvedValue({ data: { google: false } } as never);
});

describe("LoginPage", () => {
  it("signs in and opens the app", async () => {
    vi.mocked(auth.login).mockResolvedValue({ data: { access_token: "tok" } } as never);
    open();
    await fill();
    expect(await screen.findByRole("heading", { name: "Overview" })).toBeInTheDocument();
    expect(localStorage.getItem("token")).toBe("tok");
    expect(auth.login).toHaveBeenCalledWith("qa@acme.io", "correct-horse", undefined);
  });

  it("asks for the authenticator code only when the account needs it, then sends it", async () => {
    vi.mocked(auth.login).mockImplementationOnce(() => refuse(401, "two_step_required")).mockResolvedValueOnce({ data: { access_token: "tok" } } as never);
    open();
    expect(screen.queryByLabelText(/Code from your authenticator app/)).not.toBeInTheDocument();
    await fill();
    const code = await screen.findByLabelText(/Code from your authenticator app/);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();      // needing a code is a step, not an error
    await userEvent.type(code, "123456");
    await userEvent.click(screen.getByRole("button", { name: "Confirm and sign in" }));
    await waitFor(() => expect(auth.login).toHaveBeenLastCalledWith("qa@acme.io", "correct-horse", "123456"));
    expect(await screen.findByRole("heading", { name: "Overview" })).toBeInTheDocument();
  });

  it("explains a wrong password without saying which part was wrong", async () => {
    vi.mocked(auth.login).mockImplementation(() => refuse(401, "Invalid credentials"));
    open();
    await fill();
    expect(await screen.findByRole("alert")).toHaveTextContent("That email and password do not match an account.");
    expect(localStorage.getItem("token")).toBeNull();
  });

  it("tells a member to use Google when their organisation requires it", async () => {
    vi.mocked(auth.login).mockImplementation(() => refuse(403, "Your organisation requires signing in with Google. Use “Continue with Google”."));
    open();
    await fill();
    expect(await screen.findByRole("alert")).toHaveTextContent("requires signing in with Google");
  });

  it("offers Google only when the server has it set up", async () => {
    vi.mocked(auth.getSsoProviders).mockResolvedValue({ data: { google: true } } as never);
    vi.mocked(auth.ssoStartUrl).mockReturnValue("/api/v1/auth/sso/google/start");
    open();
    expect(await screen.findByRole("link", { name: "Continue with Google" })).toHaveAttribute("href", "/api/v1/auth/sso/google/start");
    expect(screen.queryByText(/Microsoft/)).not.toBeInTheDocument();
  });

  it("turns a failed Google sign-in into a plain sentence", async () => {
    open("/login?sso_error=unverified");
    expect(await screen.findByRole("alert")).toHaveTextContent("email address is not verified");
  });
});
