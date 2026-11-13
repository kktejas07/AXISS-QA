/**
 * Runs after `vite build`. A single-page app sends search engines and AI
 * assistants an empty page until its script runs, and many of them never run
 * it. This writes the landing page's real HTML into the built index.html, adds
 * the structured data they read, and writes sitemap.xml, robots.txt and
 * llms.txt for the site's public address.
 *
 *   vite-node scripts/prerender.tsx [outDir]      SITE_URL=https://example.com to change the address
 */
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { renderToString } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { faqs, site } from "../src/content/site";
import { LandingPage } from "../src/pages/LandingPage";

const out = process.argv[2] || "dist";
const url = (process.env.SITE_URL || "https://qa.vatax360.com").replace(/\/+$/, "");
const today = new Date().toISOString().slice(0, 10);

const body = renderToString(
  <MemoryRouter initialEntries={["/"]}>
    <LandingPage />
  </MemoryRouter>
);

// What search engines and answer engines read to know what this is, who makes it and what it costs to try.
const data = [
  { "@context": "https://schema.org", "@type": "Organization", name: site.name, url, logo: `${url}/brand/app-icon.png`, parentOrganization: { "@type": "Organization", name: site.maker } },
  { "@context": "https://schema.org", "@type": "WebSite", name: site.name, url },
  {
    "@context": "https://schema.org", "@type": "SoftwareApplication", name: site.name, url, description: site.description,
    applicationCategory: "DeveloperApplication", operatingSystem: "Web", image: `${url}/brand/social-card.png`,
    offers: { "@type": "Offer", price: "0", priceCurrency: "USD", description: "Free plan: one person, two scans a month" },
    featureList: ["Website security scans", "Mobile build scans", "Source code and repository scans", "API description scans", "Chatbot and AI application testing",
      "Manual test cases and automation scripts", "Pull request scans", "Scheduled scans", "OWASP Top 10 mapping", "Software bill of materials and licence check"],
  },
  { "@context": "https://schema.org", "@type": "FAQPage", mainEntity: faqs.map((f) => ({ "@type": "Question", name: f.q, acceptedAnswer: { "@type": "Answer", text: f.a } })) },
];
// "<" is escaped so nothing in the text can close the script tag.
const jsonLd = data.map((d) => `<script type="application/ld+json">${JSON.stringify(d).replace(/</g, "\\u003c")}</script>`).join("\n    ");

const file = join(out, "index.html");
let html = readFileSync(file, "utf8");
const must = (found: boolean, what: string) => {
  if (!found) throw new Error(`prerender: ${what} was not found in ${file}`);
};
must(html.includes('<div id="root"></div>'), "the empty root");
must(html.includes('content="/brand/social-card.png"'), "the social card address");
html = html
  .replace('<div id="root"></div>', `<div id="root">${body}</div>`)
  .replace('content="/brand/social-card.png"', `content="${url}/brand/social-card.png"`)
  .replace("</head>", `  <link rel="canonical" href="${url}/">\n    <meta property="og:url" content="${url}/">\n    ${jsonLd}\n  </head>`);
writeFileSync(file, html);

writeFileSync(join(out, "sitemap.xml"), `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${[["/", "1.0"], ["/pricing", "0.8"], ["/register", "0.5"], ["/login", "0.3"]].map(([path, priority]) => `  <url><loc>${url}${path}</loc><lastmod>${today}</lastmod><priority>${priority}</priority></url>`).join("\n")}
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
- [Pricing](${url}/pricing): the free plan and team plans
- [Sign up](${url}/register): create a free account

## Questions and answers

${faqs.map((f) => `### ${f.q}\n\n${f.a}`).join("\n\n")}
`);

console.log(`prerender: wrote the landing page, structured data, sitemap.xml, robots.txt and llms.txt to ${out} for ${url}`);
