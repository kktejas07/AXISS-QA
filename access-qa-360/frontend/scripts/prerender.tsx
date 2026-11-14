/**
 * Runs after `vite build`. A single-page app sends search engines and AI
 * assistants an empty page until its script runs, and many of them never run
 * it. This writes the landing page's real HTML into the built index.html, adds
 * the structured data they read, and writes sitemap.xml, robots.txt and
 * llms.txt for the site's public address.
 *
 * The guides are written out the same way, one built page each.
 *
 *   vite-node scripts/prerender.tsx [outDir]
 *
 *   SITE_URL=https://example.com            the site's public address
 *   GOOGLE_SITE_VERIFICATION=...            the code Google Search Console gives you to prove the site is yours
 *   BING_SITE_VERIFICATION=...              the same for Bing Webmaster Tools
 */
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { renderToString } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { guides } from "../src/content/guides";
import { faqs, pricingFaqs, site } from "../src/content/site";
import { GuidePage, GuidesPage } from "../src/pages/GuidesPage";
import { LandingPage } from "../src/pages/LandingPage";
import { PricingPage } from "../src/pages/PricingPage";

const out = process.argv[2] || "dist";
const url = (process.env.SITE_URL || "https://qa.vatax360.com").replace(/\/+$/, "");
const today = new Date().toISOString().slice(0, 10);

const html = (path: string, page: React.ReactElement) => renderToString(<MemoryRouter initialEntries={[path]}>{page}</MemoryRouter>);
const ld = (data: object[]) =>
  // "<" is escaped so nothing in the text can close the script tag.
  data.map((d) => `<script type="application/ld+json">${JSON.stringify(d).replace(/</g, "\\u003c")}</script>`).join("\n    ");
const attr = (text: string) => text.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");

const organization = { "@type": "Organization", name: site.name, url, logo: `${url}/brand/app-icon.png` };

// What search engines and answer engines read to know what this is, who makes it and that it is free to try.
const home = [
  { "@context": "https://schema.org", ...organization, parentOrganization: { "@type": "Organization", name: site.maker } },
  { "@context": "https://schema.org", "@type": "WebSite", name: site.name, url },
  {
    "@context": "https://schema.org", "@type": "SoftwareApplication", name: site.name, url, description: site.description,
    applicationCategory: "DeveloperApplication", operatingSystem: "Web", image: `${url}/brand/social-card.png`,
    offers: { "@type": "Offer", price: "0", priceCurrency: "USD", description: "Free plan for one person" },
    featureList: ["Website security scans", "Mobile build scans", "Source code and repository scans", "API description scans", "Chatbot and AI application testing",
      "Manual test cases and automation scripts", "Pull request scans", "Scheduled scans", "OWASP Top 10 mapping", "Software bill of materials and licence check"],
  },
  { "@context": "https://schema.org", "@type": "FAQPage", mainEntity: faqs.map((f) => ({ "@type": "Question", name: f.q, acceptedAnswer: { "@type": "Answer", text: f.a } })) },
];

const file = join(out, "index.html");
const shell = readFileSync(file, "utf8");
const must = (found: boolean, what: string) => {
  if (!found) throw new Error(`prerender: ${what} was not found in ${file}`);
};
must(shell.includes('<div id="root"></div>'), "the empty root");
must(shell.includes('content="/brand/social-card.png"'), "the social card address");
must(/<title>.*?<\/title>/.test(shell) && /<meta name="description" content="[^"]*">/.test(shell), "the title and description");

// Proof of ownership for the search engines' own consoles, when the codes are given at build time.
const proofs = [["google-site-verification", process.env.GOOGLE_SITE_VERIFICATION], ["msvalidate.01", process.env.BING_SITE_VERIFICATION]]
  .filter(([, code]) => code && /^[\w-]{8,100}$/.test(code))
  .map(([name, code]) => `<meta name="${name}" content="${code}">`).join("\n    ");

/** One built page: the shell with this page's HTML, title, description, address and structured data. */
function page(path: string, body: string, data: object[], title?: string, description?: string): string {
  let made = shell
    .replace('<div id="root"></div>', `<div id="root"${path === "/" ? "" : ` data-path="${path}"`}>${body}</div>`)
    .replace('content="/brand/social-card.png"', `content="${url}/brand/social-card.png"`)
    .replace("</head>", `  <link rel="canonical" href="${url}${path}">\n    <meta property="og:url" content="${url}${path}">\n    ${proofs ? proofs + "\n    " : ""}${ld(data)}\n  </head>`);
  if (title && description) {
    made = made
      .replace(/<title>.*?<\/title>/, `<title>${attr(title)}</title>`)
      .replace(/<meta name="description" content="[^"]*">/, `<meta name="description" content="${attr(description)}">`)
      .replace(/<meta property="og:title" content="[^"]*">/, `<meta property="og:title" content="${attr(title)}">`)
      .replace(/<meta property="og:description" content="[^"]*">/, `<meta property="og:description" content="${attr(description)}">`);
  }
  return made;
}
function write(path: string, content: string) {
  const folder = join(out, path);
  mkdirSync(folder, { recursive: true });
  writeFileSync(join(folder, "index.html"), content);
}

// The guides first: they are made from the untouched shell, which the home page then replaces.
write("/guides", page("/guides", html("/guides", <GuidesPage />),
  [{ "@context": "https://schema.org", "@type": "CollectionPage", name: "Wiseflow guides", url: `${url}/guides`,
     hasPart: guides.map((g) => ({ "@type": "Article", headline: g.title, url: `${url}/guides/${g.slug}` })) }],
  "Guides: Wiseflow", "Short, practical guides to testing and security: prompt injection, the OWASP Top 10, SBOMs, open-source licences and pull request scans."));
for (const g of guides) {
  const path = `/guides/${g.slug}`;
  write(path, page(path, html(path, <GuidePage slug={g.slug} />), [
    { "@context": "https://schema.org", "@type": "Article", headline: g.title, description: g.description, datePublished: g.updated, dateModified: g.updated,
      mainEntityOfPage: `${url}${path}`, image: `${url}/brand/social-card.png`, author: organization, publisher: organization },
    { "@context": "https://schema.org", "@type": "BreadcrumbList", itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: `${url}/` },
      { "@type": "ListItem", position: 2, name: "Guides", item: `${url}/guides` },
      { "@type": "ListItem", position: 3, name: g.title, item: `${url}${path}` }] },
  ], `${g.title}: Wiseflow`, g.description));
}
// Pricing, with the plans' built-in wording. The live page fills in the prices from the server.
write("/pricing", page("/pricing", html("/pricing", <PricingPage />),
  [{ "@context": "https://schema.org", "@type": "FAQPage", mainEntity: pricingFaqs.map((f) => ({ "@type": "Question", name: f.q, acceptedAnswer: { "@type": "Answer", text: f.a } })) }],
  "Pricing: Wiseflow", "Wiseflow plans: a free plan for one person, a Team plan per person per month with no limit on scans, and Enterprise on agreed terms."));
writeFileSync(file, page("/", html("/", <LandingPage />), home));

const listed: [string, string, string][] = [["/", "1.0", today], ["/guides", "0.8", today], ...guides.map((g): [string, string, string] => [`/guides/${g.slug}`, "0.7", g.updated]),
  ["/pricing", "0.8", today], ["/register", "0.5", today], ["/login", "0.3", today]];
writeFileSync(join(out, "sitemap.xml"), `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${listed.map(([path, priority, changed]) => `  <url><loc>${url}${path}</loc><lastmod>${changed}</lastmod><priority>${priority}</priority></url>`).join("\n")}
</urlset>
`);

const app = ["/audits", "/scans", "/admin", "/settings", "/findings", "/schedules", "/library", "/projects", "/profile", "/help", "/api/"];
writeFileSync(join(out, "robots.txt"), `# The public pages may be indexed; the app itself is behind sign-in.
User-agent: *
Allow: /
${app.map((p) => `Disallow: ${p}`).join("\n")}

# AI assistants and answer engines are welcome to read and quote the public pages.
${["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot", "Claude-User", "PerplexityBot", "Perplexity-User", "Google-Extended", "Applebot-Extended", "CCBot"]
    .map((bot) => `User-agent: ${bot}\nAllow: /\n${app.map((p) => `Disallow: ${p}`).join("\n")}\n`).join("\n")}
Sitemap: ${url}/sitemap.xml
`);

// A plain summary for AI assistants (the llms.txt convention): what the product is, in text they can quote.
writeFileSync(join(out, "llms.txt"), `# ${site.name}

> ${site.description}

${site.name} is made by ${site.maker}. It is a web application; there is nothing to install.

## Pages

- [Home](${url}/): what ${site.name} does, with screenshots
- [Guides](${url}/guides): practical explanations of testing and security topics
- [Pricing](${url}/pricing): the free plan and team plans
- [Sign up](${url}/register): create a free account

## Questions and answers

${faqs.map((f) => `### ${f.q}\n\n${f.a}`).join("\n\n")}

## Guides

${guides.map((g) => `- [${g.title}](${url}/guides/${g.slug}): ${g.description}`).join("\n")}
`);

console.log(`prerender: wrote the landing page, ${guides.length} guides, structured data, sitemap.xml, robots.txt and llms.txt to ${out} for ${url}`);
