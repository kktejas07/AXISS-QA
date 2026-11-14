/**
 * The public product pages: one for each thing Wiseflow scans. Every line says
 * what the product does today. Where it stops short, the page says so.
 */
export interface Product {
  slug: string;
  name: string;            // in menus
  title: string;           // the page's heading
  lead: string;
  input: string;           // what you give it
  finds: string[];
  gives: string[];
  limits: string;          // what it does not do
  shot?: { src: string; alt: string };
}

export const products: Product[] = [
  {
    slug: "web", name: "Websites", title: "Scan a website the way a careful tester would",
    lead: "Paste an address. Wiseflow opens the site in a real browser, maps its pages and forms, and checks them for security, accessibility and speed.",
    input: "A web address. Add sign-in details to reach pages behind a login; they are stored encrypted and deleted when the scan ends.",
    finds: [
      "Pages served, or passwords and card details sent, without encryption",
      "Input written back into a page unescaped (cross-site scripting)",
      "Sign-in cookies missing HttpOnly, Secure or SameSite",
      "Missing security headers, and server versions given away",
      "Admin pages that open without signing in",
      "Accessibility problems against WCAG 2 A and AA, by page",
      "Slow pages: time to first byte, first paint and largest paint",
    ],
    gives: ["Findings ranked by severity, each with how to fix it", "A map of the flows through the site", "Manual test cases and a Playwright script for each page", "What is new and what was fixed since the last scan", "A PDF report and a spreadsheet mapped to the OWASP Top 10"],
    limits: "A scan stays on the address you give and does not try to take a site down. It finds common problems; it is not a penetration test by a person.",
  },
  {
    slug: "mobile", name: "Mobile builds", title: "Check a mobile build before it ships",
    lead: "Upload an Android .apk or an iOS .ipa. Wiseflow reads the build and reports what it asks for and how it is set up.",
    input: "An .apk or .ipa file. A file that is not a real build is refused on upload.",
    finds: ["Permissions the app asks for, with the risky ones called out", "Insecure settings in the Android manifest or the iOS Info.plist", "Deep links and exported screens other apps can open"],
    gives: ["Findings with how to fix each", "Manual test cases for the app", "An Appium test script to start from", "A PDF report"],
    limits: "The build is read, not run. Wiseflow does not drive the app on a phone or an emulator.",
  },
  {
    slug: "code", name: "Code and repositories", title: "Read the code for secrets, risky patterns and vulnerable packages",
    lead: "Upload a .zip or link a GitHub, GitLab or Bitbucket repository. The code is read, never run.",
    input: "A .zip of source code, or a repository link. Connect GitHub to scan every pull request.",
    finds: ["Keys, passwords and tokens left in the code", "Risky code: SQL built from strings, shell commands, text run as code, debug mode", "Packages with known vulnerabilities, from the OSV database", "Routes that have no tests"],
    gives: ["Each finding with its file and line", "A software bill of materials in CycloneDX format", "The licence of each Python and JavaScript package, risky ones first", "On a pull request: a comment and a pass or fail that only counts what the change added"],
    limits: "Uploaded code is deleted when its scan finishes. The licence check covers Python and JavaScript packages; other kinds are reported as not covered.",
  },
  {
    slug: "api", name: "APIs", title: "Find the gaps in an API from its description",
    lead: "Upload an OpenAPI or Swagger file. Wiseflow reads every endpoint and reports where the design leaves a door open.",
    input: "An OpenAPI or Swagger file (.json, .yaml). Optionally the API's address, to check the live service too.",
    finds: ["Endpoints that change data but need no sign-in", "An API offered without encryption", "Sign-in endpoints with no limit on attempts documented", "Endpoints with no error responses documented"],
    gives: ["Every endpoint listed with whether it needs sign-in", "Findings ranked by severity", "Manual test cases for the endpoints", "A PDF report"],
    limits: "Without the API's address, findings come from the description alone, so they are only as accurate as that file.",
  },
  {
    slug: "chatbot", name: "Chatbots", title: "Test the AI you ship",
    lead: "Give Wiseflow your chatbot's address. It sends the messages an attacker would and shows you each reply.",
    input: "Your chatbot's https endpoint, the shape of the request, and where the reply is in the answer. Any key you give is deleted when the scan ends.",
    finds: ["Prompt injection: the bot follows instructions it was told to ignore", "Data leaks: it gives out another customer's details", "It reveals its hidden instructions", "It can be talked out of its job by role-play or rewording"],
    gives: ["Every message sent, the reply, and whether the bot held", "Replies a rule cannot judge, marked for a person to read", "Findings with how to fix each", "Test cases to run again after every change"],
    limits: "Only test a bot you own or may test. The endpoint must be a public https address.",
    shot: { src: "/landing/chatbot.webp", alt: "A chatbot scan: two test messages the bot failed and one to check by hand, each with the bot's reply" },
  },
];

export const product = (slug: string) => products.find((p) => p.slug === slug);

/** What changed, newest first. Add an entry when something a customer would notice ships. */
export const changelog: { date: string; title: string; items: string[] }[] = [
  { date: "2026-11-14", title: "Website security checks, an animated Wise, and a fuller public site", items: [
    "Website scans now check for unencrypted pages and forms, weak sign-in cookies, exposed server versions, open admin pages and cross-site scripting.",
    "Accessibility checks run on sites that block outside scripts.",
    "Scans aimed at private network addresses are refused.",
    "Wise, the owl, moves to show what it is doing.",
    "New pages: one for each kind of scan, guides, docs, pricing questions and this changelog.",
  ] },
  { date: "2026-11-14", title: "Licence check, bill of materials and a findings list", items: [
    "Code scans list every package as a CycloneDX bill of materials and check Python and JavaScript licences.",
    "One list of open findings across all your scans, each with a status and an owner that carry over to later scans.",
    "A notification bell for finished scans and a getting-started checklist.",
    "A profile page and a help page.",
  ] },
  { date: "2026-11-13", title: "Chatbot testing and your own AI provider", items: [
    "A new kind of scan that tests your own chatbot for prompt injection and data leaks.",
    "Bring your own key for Claude, ChatGPT, Gemini, Grok, Mistral, DeepSeek, Groq or OpenRouter.",
    "Wise can start a scan or add a schedule for you, after you confirm.",
    "A smoke test that opens each page of a scanned site and reports the ones that fail.",
  ] },
  { date: "2026-11-13", title: "Schedules, pull request scans and Wise", items: [
    "Scan on a timetable, with a message in Slack or Teams saying what is new and what was fixed.",
    "Scan every GitHub pull request, with a comment and a pass or fail.",
    "Findings sorted under the OWASP Top 10.",
    "Wise answers questions from your scans and documents, with its sources.",
    "Scans behind a login, page speed, API description scans and two-step sign-in.",
  ] },
];
