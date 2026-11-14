import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { guide } from "../content/guides";
import { site } from "../content/site";

// The pages anyone can open. Everything else is the signed-in app and is kept out of search results.
const pages: Record<string, { title: string; description: string; index: boolean }> = {
  "/": { title: site.title, description: site.description, index: true },
  "/pricing": { title: "Pricing: Wiseflow", description: "Wiseflow plans: a free plan for one person, a Team plan per person per month with no limit on scans, and Enterprise on agreed terms.", index: true },
  "/register": { title: "Create a free account: Wiseflow", description: "Start scanning websites, mobile builds, code, APIs and chatbots on Wiseflow's free plan. No card needed.", index: true },
  "/guides": { title: "Guides: Wiseflow", description: "Short, practical guides to testing and security: prompt injection, the OWASP Top 10, SBOMs, open-source licences and pull request scans.", index: true },
  "/login": { title: "Sign in: Wiseflow", description: "Sign in to your Wiseflow workspace.", index: true },
  // Drafts until a lawyer has reviewed them, so they are not offered to search engines yet.
  "/privacy": { title: "Privacy: Wiseflow", description: "How Wiseflow handles your data.", index: false },
  "/terms": { title: "Terms: Wiseflow", description: "The terms for using Wiseflow.", index: false },
};

function set(selector: string, make: () => HTMLElement, attribute: string, value: string) {
  let el = document.head.querySelector<HTMLElement>(selector);
  if (!el) {
    el = make();
    document.head.appendChild(el);
  }
  el.setAttribute(attribute, value);
}

/** Keeps the tab title, description, canonical address and "may this be indexed" flag right for the page being shown. */
export function RouteMeta() {
  const { pathname } = useLocation();
  useEffect(() => {
    const signedOutHome = pathname === "/" && !localStorage.getItem("token");
    const path = pathname.replace(/\/+$/, "") || "/";
    const article = path.startsWith("/guides/") ? guide(path.slice(8)) : undefined;
    const page = article
      ? { title: `${article.title}: Wiseflow`, description: article.description, index: true }
      : path === "/" ? (signedOutHome ? pages["/"] : undefined) : pages[path];
    document.title = page?.title ?? site.name;
    const meta = (name: string) => () => Object.assign(document.createElement("meta"), { name });
    set('meta[name="description"]', meta("description"), "content", page?.description ?? site.description);
    set('meta[name="robots"]', meta("robots"), "content", page?.index ? "index, follow" : "noindex, nofollow");
    set('link[rel="canonical"]', () => Object.assign(document.createElement("link"), { rel: "canonical" }), "href", `${location.origin}${page ? path : "/"}`);
  }, [pathname]);
  return null;
}
