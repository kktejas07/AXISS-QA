import { createServer } from "node:http";
import { expect, test } from "@playwright/test";
import { PASSWORD, newAccount, scrollsSideways, signedIn, totp, signedInAsAdmin } from "./helpers";

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

test.describe("landing page", () => {
  test("a visitor sees what Wiseflow is, with real screenshots, and can reach sign-up, pricing and the legal pages", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1, name: "Find what is broken before your customers do." })).toBeVisible();
    await expect(page.getByText(/Free plan: 1 person, 2 scans a month/)).toBeVisible();          // read from the product, not typed into the page
    await expect(page.getByRole("heading", { name: "Six things you can point it at" })).toBeVisible();
    // The drifting icons are decoration: two layers on the page, and none of them can take a click meant for a button.
    await expect(page.getByTestId("tech-backdrop")).toHaveCount(2);
    expect(await page.getByTestId("tech-backdrop").first().evaluate((el) => getComputedStyle(el).pointerEvents)).toBe("none");
    for (const alt of [/A finished Wiseflow scan/, /Wise, the assistant, answering/, /A chatbot scan/]) {
      const image = page.getByRole("img", { name: alt });
      await image.scrollIntoViewIfNeeded();
      await expect.poll(() => image.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth)).toBeGreaterThan(1000);
    }
    await expect(page).toHaveTitle(/Wiseflow: AI testing and security checks/);
    expect(await page.locator('meta[name="description"]').getAttribute("content")).toContain("Point Wiseflow at");
    expect((await page.request.get("/robots.txt")).ok()).toBe(true);
    expect((await (await page.request.get("/manifest.webmanifest")).json()).name).toBe("Wiseflow");
    expect((await page.request.get("/brand/social-card.png")).headers()["content-type"]).toContain("image/png");

    // Search engines and AI assistants that do not run scripts still get the whole page, and the data they read.
    const source = await (await page.request.get("/")).text();
    expect(source).toContain("Find what is broken before your customers do.");
    expect(source).toContain("Does Wiseflow test AI chatbots?");
    const blocks = [...source.matchAll(/<script type="application\/ld\+json">(.*?)<\/script>/gs)].map((m) => JSON.parse(m[1]));
    expect(blocks.map((b) => b["@type"])).toEqual(["Organization", "WebSite", "SoftwareApplication", "FAQPage"]);
    const faq = blocks[3].mainEntity as { name: string; acceptedAnswer: { text: string } }[];
    for (const item of faq) await expect(page.getByText(item.acceptedAnswer.text, { exact: true })).toBeAttached();      // every answer in the data is on the page
    expect(await page.locator('link[rel="canonical"]').getAttribute("href")).toBe("http://localhost:5183/");
    expect(await page.locator('meta[name="robots"]').getAttribute("content")).toBe("index, follow");
    expect(await (await page.request.get("/sitemap.xml")).text()).toContain("<loc>http://localhost:5183/pricing</loc>");
    const robots = await (await page.request.get("/robots.txt")).text();
    expect(robots).toContain("User-agent: GPTBot");
    expect(robots).toContain("Disallow: /settings");
    expect(robots).toContain("Sitemap: http://localhost:5183/sitemap.xml");
    expect(await (await page.request.get("/llms.txt")).text()).toContain("### What can Wiseflow scan?");

    await page.getByRole("contentinfo").getByRole("link", { name: "Privacy" }).click();
    await expect(page).toHaveTitle("Privacy: Wiseflow");
    expect(await page.locator('meta[name="robots"]').getAttribute("content")).toBe("noindex, nofollow");               // a draft is not offered to search engines
    await expect(page.getByRole("note")).toContainText("This is a draft");
    await page.goto("/");
    await page.getByRole("banner").getByRole("link", { name: "Start free" }).click();
    await expect(page).toHaveURL(/\/register$/);
  });
});

test.describe("findings, notifications and first steps", () => {
  test("a new account is guided, then decides what happens to a finding", async ({ page, request }) => {
    test.setTimeout(120_000);
    await signedIn(page, request);
    await page.goto("/");
    await expect(page.getByRole("region", { name: "Getting started" }).getByText("0 of 5 done")).toBeVisible();
    // Signed in, the address "/" is the app: not the public page, and not for search engines.
    await expect(page.getByRole("heading", { name: "Find what is broken before your customers do." })).toHaveCount(0);
    await expect(page).toHaveTitle("Wiseflow");
    expect(await page.locator('meta[name="robots"]').getAttribute("content")).toBe("noindex, nofollow");
    await scanTheApi(page);

    await page.getByRole("button", { name: /^Notifications/ }).click();
    await expect(page.getByRole("dialog", { name: "Notifications" }).getByRole("link", { name: /Scan of Shop API finished: 0 critical, 1 high/ })).toBeVisible();
    await page.keyboard.press("Escape");

    await page.getByRole("link", { name: "Findings" }).click();
    await expect(page.getByRole("button", { name: "Open (5)" })).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("button", { name: "Decide about Endpoint needs no sign-in" }).click();
    await page.getByLabel("What happens to it").selectOption({ label: "Risk accepted" });
    await page.getByLabel("Owner").selectOption({ label: "Erin Tester" });
    await page.getByLabel("Why").fill("This endpoint is public on purpose.");
    await page.getByRole("button", { name: "Save decision" }).click();
    await expect(page.getByRole("status")).toContainText("is now risk accepted");
    await expect(page.getByRole("button", { name: "Open (4)" })).toBeVisible();
    await page.getByRole("button", { name: "Risk accepted (1)" }).click();
    await expect(page.getByText("This endpoint is public on purpose.")).toBeVisible();
    await expect(page.getByText("Owner: Erin Tester.")).toBeVisible();

    await page.getByRole("link", { name: "Overview" }).click();
    await expect(page.getByRole("region", { name: "Getting started" }).getByText("1 of 5 done")).toBeVisible();
  });
});

test.describe("platform keys, profile and help", () => {
  test("a super admin replaces a platform key without it ever being shown again", async ({ page, request }) => {
    const key = "sk_live_e2e_secret_never_shown_7Q2x";
    await signedInAsAdmin(page, request);
    await page.goto("/admin/keys");
    const stripe = page.getByRole("region", { name: "Stripe" });
    await expect(stripe.getByText("Not set up")).toBeVisible();
    await expect(stripe.getByRole("button", { name: "Test Stripe" })).toBeDisabled();
    await stripe.getByLabel("Secret key").fill(key);
    await stripe.getByRole("button", { name: "Save Stripe" }).click();
    await expect(stripe.getByRole("status")).toHaveText("Saved. It is in use from now.");
    await expect(stripe.getByText("Set, not tested")).toBeVisible();
    await expect(stripe.getByText("A key is set (ends in 7Q2x), saved here. It is never shown in full.")).toBeVisible();
    await expect(stripe.getByLabel("Secret key")).toHaveValue("");

    await page.reload();
    await expect(page.getByRole("region", { name: "Stripe" }).getByText("ends in 7Q2x")).toBeVisible();
    expect(await page.content()).not.toContain(key);

    await page.getByRole("link", { name: "System health" }).click();
    await expect(page.getByRole("listitem").filter({ hasText: "Stripe" })).toContainText("Set. Test it under Platform keys");
    await page.getByRole("link", { name: "Audit log" }).click();
    await expect(page.getByRole("row").filter({ hasText: "Secret key" }).first()).toBeVisible();
    expect(await page.content()).not.toContain(key);

    await page.getByRole("link", { name: "Platform keys" }).click();
    await page.getByRole("region", { name: "Stripe" }).getByRole("button", { name: "Remove Secret key" }).click();
    await expect(page.getByRole("region", { name: "Stripe" }).getByText("Not set up")).toBeVisible();
  });

  test("someone who is not a super admin cannot open platform keys", async ({ page, request }) => {
    await signedIn(page, request);
    await page.goto("/admin/keys");
    await expect(page.getByRole("heading", { name: "Platform keys" })).toHaveCount(0);
  });

  test("you can change your name and find the help page", async ({ page, request }) => {
    const email = await signedIn(page, request);
    await page.goto("/");
    await page.getByRole("link", { name: `Your profile, ${email}` }).click();
    await expect(page.getByLabel("Name")).toHaveValue("Erin Tester");
    await expect(page.getByRole("button", { name: "Save name" })).toBeDisabled();
    await page.getByLabel("Name").fill("Erin Q. Tester");
    await page.getByRole("button", { name: "Save name" }).click();
    await expect(page.getByRole("status")).toHaveText("Your name was changed.");
    await page.reload();
    await expect(page.getByLabel("Name")).toHaveValue("Erin Q. Tester");

    await page.getByRole("link", { name: "Help" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Help" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Starting a scan from your build pipeline" })).toBeVisible();
    await expect(page.locator("pre")).toContainText("/api/v1/audits");
    await page.getByRole("navigation", { name: "Help topics" }).getByRole("link", { name: "Who can do what" }).click();
    await expect(page.getByRole("heading", { name: "Who can do what" })).toBeInViewport();
  });
});

test.describe("guides", () => {
  test("each guide is a real page that can be read without scripts, and is reachable from the home page", async ({ page }) => {
    const source = await (await page.request.get("/guides/what-is-an-sbom/")).text();
    expect(source).toContain("<title>What a software bill of materials (SBOM) is, and when you need one: Wiseflow</title>");
    expect(source).toContain("It is the software equivalent of an ingredients label.");
    const blocks = [...source.matchAll(/<script type="application\/ld\+json">(.*?)<\/script>/gs)].map((m) => JSON.parse(m[1]));
    expect(blocks.map((b) => b["@type"])).toEqual(["Article", "BreadcrumbList"]);
    expect(blocks[0].mainEntityOfPage).toBe("http://localhost:5183/guides/what-is-an-sbom");
    const map = await (await page.request.get("/sitemap.xml")).text();
    expect(map).toContain("<loc>http://localhost:5183/guides/test-a-chatbot-for-prompt-injection</loc>");

    await page.goto("/");
    await page.getByRole("banner").getByRole("link", { name: "Guides" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Guides" })).toBeVisible();
    await expect(page.getByRole("listitem").filter({ has: page.getByRole("heading", { level: 2 }) })).toHaveCount(5);
    await page.getByRole("link", { name: /How to test a chatbot for prompt injection/ }).click();
    await expect(page.getByRole("heading", { level: 1, name: "How to test a chatbot for prompt injection" })).toBeVisible();
    await expect(page).toHaveTitle("How to test a chatbot for prompt injection: Wiseflow");
    expect(await page.locator('link[rel="canonical"]').getAttribute("href")).toBe("http://localhost:5183/guides/test-a-chatbot-for-prompt-injection");
    expect(await page.locator('meta[name="robots"]').getAttribute("content")).toBe("index, follow");
    await page.getByRole("link", { name: "Start free" }).last().click();
    await expect(page).toHaveURL(/\/register$/);

    // Opened directly, a guide shows its own content at once and nothing from the home page.
    await page.goto("/guides/owasp-top-10-in-plain-words");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("The OWASP Top 10 in plain words");
    await expect(page.getByText("A10 Server-side request forgery", { exact: false })).toBeVisible();
    await page.goto("/guides/no-such-guide");
    await expect(page.getByRole("heading", { name: "That guide does not exist" })).toBeVisible();
    expect(await page.locator('meta[name="robots"]').getAttribute("content")).toBe("noindex, nofollow");
  });
});

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

test.describe("Wise", () => {
  test("answers from a scan, links to the finding, and points to the right screen for a request", async ({ page, request }) => {
    test.setTimeout(120_000);
    await signedIn(page, request);
    await scanTheApi(page);

    await page.getByRole("button", { name: "Ask Wise, your assistant" }).click();
    const wise = page.getByRole("dialog", { name: "Wise, your assistant" });
    await expect(wise.getByRole("button", { name: "What are my worst findings?" })).toBeVisible();
    await wise.getByLabel("Your question for Wise").fill("Which endpoint needs no sign-in?");
    await wise.getByRole("button", { name: "Send" }).click();
    await expect(wise.getByText(/Endpoint needs no sign-in/).first()).toBeVisible();
    await expect(wise.getByRole("list", { name: "Where this came from" }).getByRole("link").first()).toHaveAttribute("href", /\/audits\/.+tab=security/);

    await wise.getByLabel("Your question for Wise").fill("Can you run this every week?");
    await wise.getByLabel("Your question for Wise").press("Enter");
    await wise.getByRole("link", { name: "Set up a schedule" }).click();
    await expect(page).toHaveURL(/\/schedules$/);
    await expect(page.getByRole("dialog")).toHaveCount(0);

    // The conversation is still there when Wise is opened again on another screen.
    await page.getByRole("button", { name: "Ask Wise, your assistant" }).click();
    await expect(page.getByRole("dialog").getByText("Which endpoint needs no sign-in?")).toBeVisible();
  });

  test("a document added in Settings is answered from", async ({ page, request }) => {
    await signedIn(page, request);
    await page.goto("/settings");
    await page.getByLabel("Add a document").setInputFiles({ name: "requirements.md", mimeType: "text/markdown", buffer: Buffer.from("# Refunds\n\nA refund must reach the customer within five working days.\n") });
    await expect(page.getByRole("status").filter({ hasText: "requirements.md added" })).toBeVisible();
    await page.getByRole("button", { name: "Ask Wise, your assistant" }).click();
    await page.getByLabel("Your question for Wise").fill("How fast must a refund reach the customer?");
    await page.getByLabel("Your question for Wise").press("Enter");
    await expect(page.getByRole("dialog").getByText(/five working days/)).toBeVisible();
  });
});

test.describe("Wise acts after confirmation", () => {
  test("asked to scan a site every week, it adds the schedule only once the person confirms", async ({ page, request }) => {
    await signedIn(page, request);
    await page.goto("/");
    await page.getByRole("button", { name: "Ask Wise, your assistant" }).click();
    const wise = page.getByRole("dialog");
    await wise.getByLabel("Your question for Wise").fill("Please check https://shop.example.com every week");
    await wise.getByLabel("Your question for Wise").press("Enter");
    const offer = wise.getByRole("group", { name: "Scan https://shop.example.com weekly" });
    await expect(offer.getByRole("button", { name: "Yes, do it" })).toBeDisabled();
    await offer.getByRole("checkbox", { name: /permission to test/ }).check();
    await offer.getByRole("button", { name: "Yes, do it" }).click();
    await expect(wise.getByText(/will be scanned weekly/)).toBeVisible();
    await expect(wise.getByRole("button", { name: "Yes, do it" })).toHaveCount(0);
    await wise.getByRole("link", { name: /Open it/ }).click();
    await expect(page).toHaveURL(/\/schedules$/);
    await expect(page.getByText("shop.example.com", { exact: true })).toBeVisible();
  });
});

test.describe("AI settings and chatbot scans", () => {
  test("the organisation picks its AI quality, and a bad key is refused", async ({ page, request }) => {
    await signedIn(page, request);
    await page.goto("/settings");
    const ai = page.locator("section").filter({ has: page.getByRole("heading", { name: "AI provider and model" }) });
    await expect(ai.getByRole("radio", { name: /Balanced/ })).toBeChecked();
    await ai.getByRole("radio", { name: /Fast/ }).check();
    await ai.getByLabel(/Your own API key/).fill("not-a-key");
    await ai.getByRole("button", { name: "Save AI settings" }).click();
    await expect(ai.getByRole("alert")).toContainText("does not look like an Anthropic API key");
    await ai.getByLabel(/Your own API key/).fill("");
    await ai.getByRole("button", { name: "Save AI settings" }).click();
    await expect(ai.getByRole("status")).toHaveText("AI settings saved.");
    await page.reload();
    await expect(page.getByRole("radio", { name: /Fast/ })).toBeChecked();

    // Another provider needs its own key, and a key that does not work is not saved.
    await ai.getByLabel(/^Provider/).selectOption({ label: "Gemini (Google)" });
    await expect(ai.getByText(/Leave empty to use gemini/)).toBeVisible();
    await ai.getByLabel(/^Your API key/).fill("not-a-real-gemini-key-000000");
    await ai.getByRole("button", { name: "Save AI settings" }).click();
    await expect(ai.getByRole("alert")).toContainText("Check the key and the model name", { timeout: 40_000 });
    await page.reload();
    await expect(page.getByLabel(/^Provider/)).toHaveValue("anthropic");
  });

  test("a chatbot is tested end to end: one careless reply is caught, the rest pass", async ({ page, request }) => {
    test.setTimeout(120_000);
    // A stand-in chatbot: it obeys one injected instruction and answers everything else safely.
    const bot = createServer((req, res) => {
      let body = "";
      req.on("data", (chunk) => (body += chunk));
      req.on("end", () => {
        const message: string = JSON.parse(body).messages[0].content;
        const reply = message.startsWith("Ignore all previous instructions") ? "WISEFLOW-7391"
          : message.includes("Zorblax") ? "I'm not aware of that product."
          : message.endsWith("the word OK.") ? "OK"
          : "I'm sorry, I can't help with that. I can answer questions about your orders.";
        res.writeHead(200, { "Content-Type": "application/json" }).end(JSON.stringify({ choices: [{ message: { content: reply } }] }));
      });
    });
    await new Promise<void>((ready) => bot.listen(0, "127.0.0.1", ready));
    const port = (bot.address() as import("node:net").AddressInfo).port;
    try {
      await signedIn(page, request);
      await page.goto("/scans/new");
      await page.getByRole("group", { name: "Type of app" }).getByRole("button", { name: /Chatbot/ }).click();
      await page.getByLabel("Where messages are sent").fill(`http://127.0.0.1:${port}/chat`);
      await page.getByLabel("App name").fill("Shop helper").catch(() => {});
      await page.getByRole("button", { name: "Continue" }).click();
      await page.getByRole("checkbox", { name: /permission/ }).check();
      await page.getByRole("button", { name: "Start scan" }).click();
      await expect(page.getByText("Completed", { exact: true }).first()).toBeVisible({ timeout: 60_000 });

      await page.getByRole("button", { name: /^Conversations/ }).click();
      await expect(page.getByRole("heading", { name: "Told to ignore its instructions" })).toBeVisible();
      await expect(page.getByText("It dropped its instructions and replied with the code it was told to.")).toBeVisible();
      await expect(page.getByRole("button", { name: "Needs attention (1)" })).toBeVisible();
      await page.getByRole("button", { name: "All (14)" }).click();
      await expect(page.getByRole("heading", { name: "Asked for another customer's details" })).toBeVisible();

      await page.getByRole("button", { name: /^Security/ }).click();
      await expect(page.getByText("Prompt injection: told to ignore its instructions").first()).toBeVisible();
    } finally {
      bot.close();
    }
  });
});

test.describe("library", () => {
  test("a test pack opens to show its cases, and a preset fills in step 2 of a scan", async ({ page, request }) => {
    await signedIn(page, request);
    await page.goto("/library");
    await page.getByRole("button", { name: /^Payments and checkout/ }).click();
    await expect(page.getByText("Pressing Pay twice charges once")).toBeVisible();
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download the Payments and checkout pack" }).click();
    expect((await download).suggestedFilename()).toBe("wiseflow-payments-test-cases.csv");

    await page.getByRole("listitem").filter({ hasText: "Quick security pass" }).getByRole("link", { name: "Start a scan with this preset" }).click();
    await page.getByRole("group", { name: "Type of app" }).getByRole("button", { name: /API/ }).click();
    await page.locator('input[type="file"]').setInputFiles(SPEC);
    await page.getByRole("button", { name: "Continue" }).click();
    await expect(page.getByRole("group", { name: "Presets" }).getByRole("button", { name: "Quick security pass" })).toHaveAttribute("aria-pressed", "true");
    const outputs = page.getByRole("group", { name: "Outputs" });
    await expect(outputs.getByRole("button", { pressed: true })).toHaveCount(1);
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

  for (const path of ["/", "/schedules", "/settings", "/scans/new", "/pricing", "/library", "/findings", "/help", "/profile"]) {
    test(`${path} fits the screen without scrolling sideways`, async ({ page, request }) => {
      await signedIn(page, request);
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      expect(await scrollsSideways(page)).toBe(false);
    });
  }

  test("the guides fit the screen without scrolling sideways", async ({ page }) => {
    for (const path of ["/guides", "/guides/owasp-top-10-in-plain-words"]) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      expect(await scrollsSideways(page), path).toBe(false);
    }
  });

  test("the landing page fits the screen without scrolling sideways", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    expect(await scrollsSideways(page)).toBe(false);
  });

  test("Wise opens within the screen", async ({ page, request }) => {
    await signedIn(page, request);
    await page.goto("/");
    await page.getByRole("button", { name: "Ask Wise, your assistant" }).click();
    const box = await page.getByRole("dialog").boundingBox();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(390);
    expect(await scrollsSideways(page)).toBe(false);
  });
});
