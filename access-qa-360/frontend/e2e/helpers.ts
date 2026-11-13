import { createHmac } from "node:crypto";
import type { APIRequestContext, Page } from "@playwright/test";

export const API = "http://localhost:8010/api/v1";
export const PASSWORD = "e2e-test-password";
let counter = 0;

/** Registers a fresh account through the API and returns its email. Each test gets its own, so tests do not share scan allowances. */
export async function newAccount(request: APIRequestContext): Promise<string> {
  const email = `e2e-${Date.now()}-${counter++}@wiseflow-e2e.io`;
  const made = await request.post(`${API}/auth/register`, { data: { email, password: PASSWORD, full_name: "Erin Tester" } });
  if (!made.ok()) throw new Error(`register failed: ${made.status()} ${await made.text()}`);
  return email;
}

/** Opens the app already signed in as a fresh account. */
export async function signedIn(page: Page, request: APIRequestContext): Promise<string> {
  const email = await newAccount(request);
  const token = (await (await request.post(`${API}/auth/login`, { data: { email, password: PASSWORD } })).json()).access_token;
  await page.addInitScript((t) => localStorage.setItem("token", t), token);
  return email;
}

/** The six-digit code an authenticator app would show for this key right now (RFC 6238). */
export function totp(secret: string, at = Date.now()): string {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const ch of secret.replace(/\s+/g, "")) bits += alphabet.indexOf(ch).toString(2).padStart(5, "0");
  const key = Buffer.from(bits.match(/.{8}/g)!.map((b) => parseInt(b, 2)));
  const counterBytes = Buffer.alloc(8);
  counterBytes.writeBigUInt64BE(BigInt(Math.floor(at / 30000)));
  const digest = createHmac("sha1", key).update(counterBytes).digest();
  const offset = digest[digest.length - 1] & 0x0f;
  return String((digest.readUInt32BE(offset) & 0x7fffffff) % 1_000_000).padStart(6, "0");
}

/** True when the page is wider than the screen, which would make it scroll sideways. */
export const scrollsSideways = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
