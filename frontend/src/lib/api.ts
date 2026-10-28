/**
 * Base URL of the backend API.
 *
 * Set EXPO_PUBLIC_API_URL when building (it is inlined at build time), e.g.
 *   EXPO_PUBLIC_API_URL=https://api.your-domain.com
 *
 * Locally it defaults to the API running on port 3000.
 */
const rawBaseUrl =
  process.env.EXPO_PUBLIC_API_URL?.trim() || "http://localhost:3000";

export const API_BASE_URL = rawBaseUrl.replace(/\/+$/, "");

const REQUEST_TIMEOUT_MS = 10_000;

export type HealthResponse = {
  status: "ok" | "degraded";
  db: "up" | "down";
  uptime: number;
  timestamp: string;
};

export type WaitlistResponse = {
  ok: true;
  email: string;
  alreadyRegistered: boolean;
  message: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
      signal: controller.signal,
    });

    const data = (await response.json().catch(() => null)) as
      | (Record<string, unknown> & { error?: string })
      | null;

    if (!response.ok) {
      throw new Error(data?.error ?? `Request failed (${response.status})`);
    }

    return data as T;
  } finally {
    clearTimeout(timeout);
  }
}

export function getHealth() {
  return request<HealthResponse>("/api/health");
}

export function getWaitlistCount() {
  return request<{ count: number }>("/api/waitlist/count");
}

export function joinWaitlist(email: string) {
  return request<WaitlistResponse>("/api/waitlist", {
    method: "POST",
    body: JSON.stringify({ email, source: "coming-soon" }),
  });
}
