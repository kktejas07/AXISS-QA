import { expect, test } from "@playwright/test";
import { PASSWORD, newAccount, scrollsSideways, signedIn, totp } from "./helpers";

const SPEC = "e2e/fixtures/shop-api.yaml";

/** Uploads the sample API description and runs the scan to the end. Leaves the page on the results. */
async function scanTheApi(page: import("@playwright/test").Page) {
  await page.goto("/scans/new");
  await page.getByRole("group", { name: "Type of app" }).getByRole("button", { name: /API/ }).click();
  await page.locator('input[type="file"]').setInputFiles(SPEC);
  await page.getByRole("button", { name: /Continue|Next/ }).click();
  await expect(page).toHaveURL(/\/audits\/.+\/setup/);
  await page.getByRole("checkbox", { name: /permission/ }).check();
  await page.getByRole("button", { name: "Start scan" }).click();
  await expect(page.getByText("Completed", { exact: true }).first()).toBeVisible({ timeout: 45_000 });
}

test.describe("signed out", () => {
  test("pricing shows the free plan's two scans, and sign-in offers no Microsoft button", async ({ page }) => {
    await page.goto("/pricing");
    await expect(page.getByText("2 scans a month")).toBeVisible();
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
    await expect(page.getByText(/Microsoft/)).toHaveCount(0);
  });

  test("a wrong password is refused and the right one opens the overview", async ({ page, request }) => {
    const email = await newAccount(request);
    await page.goto("/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill("not-the-password");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("alert")).toContainText("do not match an account");
    await page.getByLabel("Password").fill(PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("heading", { name: "No scans yet" })).toBeVisible();
    await expect(page.locator("svg[role=presentation]").first()).toBeVisible();      // the empty-state illustration
  });
});

test.describe("scanning an API description", () => {
  test("upload, scan, read the results, compare a second scan, and hit the free limit on the third", async ({ page, request }) => {
    test.setTimeout(180_000);
    await signedIn(page, request);
    await scanTheApi(page);
    await expect(page.getByRole("heading", { name: "Shop API" })).toBeVisible();

    await page.getByRole("button", { name: /^Security/ }).click();
    await expect(page.getByText("Endpoint needs no sign-in").first()).toBeVisible();

    await page.getByRole("button", { name: /^Endpoints/ }).click();
    await expect(page.getByText("2 of 4 endpoints need sign-in")).toBeVisible();
    await expect(page.getByRole("cell", { name: "/orders/{id}" }).first()).toBeVisible();

    await page.getByRole("button", { name: /^Standards/ }).click();
    const auth = page.getByRole("button", { name: /A07.*authentication failures/ });
    await auth.click();
    await expect(auth).toHaveAttribute("aria-expanded", "true");

    await page.getByRole("button", { name: /^Test cases/ }).click();
    await expect(page.getByText("GET /orders works with valid input").first()).toBeVisible();

    await page.getByRole("button", { name: /^Changes/ }).click();
    await expect(page.getByRole("heading", { name: "Nothing to compare with yet" })).toBeVisible();

    // The second scan of the same API is compared with the first.
    await scanTheApi(page);
    await page.getByRole("button", { name: /^Changes/ }).click();
    await expect(page.getByText("Nothing new was found.")).toBeVisible();
    await expect(page.getByRole("img", { name: /Risk score for the last 2 scans/ })).toBeVisible();

    // A free account has two scans a month.
    await page.goto("/scans/new");
    await page.getByRole("group", { name: "Type of app" }).getByRole("button", { name: /API/ }).click();
    await page.locator('input[type="file"]').setInputFiles(SPEC);
    await page.getByRole("button", { name: /Continue|Next/ }).click();
    await page.getByRole("checkbox", { name: /permission/ }).check();
    await page.getByRole("button", { name: "Start scan" }).click();
    await expect(page.getByRole("alert")).toContainText("used all 2 scans for this month");
  });

  test("a file that is not an API description is refused with a reason", async ({ page, request }) => {
    await signedIn(page, request);
    await page.goto("/scans/new");
    await page.getByRole("group", { name: "Type of app" }).getByRole("button", { name: /API/ }).click();
    await page.locator('input[type="file"]').setInputFiles({ name: "notes.yaml", mimeType: "text/yaml", buffer: Buffer.from("hello: world\n") });
    await page.getByRole("button", { name: /Continue|Next/ }).click();
    await expect(page.getByRole("alert")).toContainText("does not look like an OpenAPI or Swagger file");
  });
});

test.describe("schedules", () => {
  test("add a weekly scan, pause it, resume it and delete it", async ({ page, request }) => {
    await signedIn(page, request);
    await page.goto("/schedules");
    await expect(page.getByRole("heading", { name: "No scheduled scans yet" })).toBeVisible();
    await page.getByRole("button", { name: "Add a schedule" }).first().click();
    await page.getByLabel("Web address").fill("https://shop.example.com");
    await expect(page.getByRole("button", { name: "Add schedule" })).toBeDisabled();
    await page.getByRole("checkbox").check();
    await page.getByRole("button", { name: "Add schedule" }).click();
    await expect(page.getByRole("status")).toHaveText("Schedule added.");
    await expect(page.getByText("shop.example.com", { exact: true })).toBeVisible();
    await expect(page.getByText(/Every week, next on/)).toBeVisible();

    await page.getByRole("button", { name: "Pause" }).click();
    await expect(page.getByText("Every week, paused")).toBeVisible();
    await page.getByRole("button", { name: "Resume" }).click();
    await expect(page.getByText(/Every week, next on/)).toBeVisible();

    await page.getByRole("button", { name: /Delete the schedule/ }).click();
    await expect(page.getByRole("heading", { name: "No scheduled scans yet" })).toBeVisible();
  });

  test("a repository link that is not on a known host is refused", async ({ page, request }) => {
    await signedIn(page, request);
    await page.goto("/schedules");
    await page.getByRole("button", { name: "Add a schedule" }).first().click();
    await page.getByText("A repository").click();
    await page.getByLabel("Repository link").fill("https://example.com/acme/shop");
    await page.getByRole("checkbox").check();
    await page.getByRole("button", { name: "Add schedule" }).click();
    await expect(page.getByRole("alert")).toContainText("GitHub, GitLab or Bitbucket");
  });
});

test.describe("settings", () => {
  test("two-step sign-in: set it up, then sign in with a code", async ({ page, request }) => {
    const email = await signedIn(page, request);
    await page.goto("/settings");
    await page.getByRole("button", { name: "Set up two-step sign-in" }).click();
    await expect(page.getByRole("img", { name: /QR code/ })).toBeVisible();
    const secret = (await page.locator("code").filter({ hasText: /^[A-Z2-7 ]{20,}$/ }).innerText()).replace(/\s+/g, "");
    await page.getByLabel("Six-digit code").fill("000000");
    await page.getByRole("button", { name: "Turn on" }).click();
    await expect(page.getByRole("alert")).toContainText("That code is not right");
    await page.getByLabel("Six-digit code").fill(totp(secret, Date.now() - 30_000));     // the previous code is still accepted
    await page.getByRole("button", { name: "Turn on" }).click();
    await expect(page.getByRole("status").filter({ hasText: "Two-step sign-in is on" })).toBeVisible();

    // A new browser session: the password alone is no longer enough.
    const fresh = await page.context().browser()!.newContext();
    const login = await fresh.newPage();
    await login.goto("http://localhost:5183/login");
    await login.getByLabel("Email").fill(email);
    await login.getByLabel("Password").fill(PASSWORD);
    await login.getByRole("button", { name: "Sign in" }).click();
    await login.getByLabel(/Code from your authenticator app/).fill(totp(secret));
    await login.getByRole("button", { name: "Confirm and sign in" }).click();
    await expect(login.getByRole("heading", { name: "No scans yet" })).toBeVisible();
    await fresh.close();
  });

  test("connections refuse an address that is not a real Slack webhook", async ({ page, request }) => {
    await signedIn(page, request);
    await page.goto("/settings");
    const slack = page.getByRole("listitem").filter({ hasText: "Post scan results to a Slack channel." });
    await expect(slack.getByText("Not connected")).toBeVisible();
    await slack.getByRole("button", { name: "Connect" }).click();
    await slack.getByLabel("Incoming webhook address").fill("https://example.com/hooks/abc");
    await slack.getByRole("button", { name: "Connect Slack" }).click();
    await expect(page.getByRole("alert").filter({ hasText: "That is not a Slack webhook address" })).toBeVisible();
  });
});

test.describe("on a phone", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  for (const path of ["/", "/schedules", "/settings", "/scans/new", "/pricing"]) {
    test(`${path} fits the screen without scrolling sideways`, async ({ page, request }) => {
      await signedIn(page, request);
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      expect(await scrollsSideways(page)).toBe(false);
    });
  }
});
