import { TechBackdrop } from "../components/TechBackdrop";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Bot, Braces, CalendarClock, Check, Code2, GitBranch, GitPullRequest, Globe, Inbox, ShieldCheck, Smartphone } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { getPlans } from "../api/billing";
import { faqs } from "../content/site";
import { BranchCheck, CompareSheets, Plugs } from "../components/Illustrations";
import { Logo } from "../components/Logo";
import { WiseBot } from "../components/WiseBot";

const targets: [LucideIcon, string, string][] = [
  [Globe, "A website", "Paste the address. Pages behind a login too."],
  [Smartphone, "A mobile build", "Upload an Android .apk or iOS .ipa."],
  [Code2, "Source code", "Upload a .zip. It is read, never run."],
  [GitBranch, "A repository", "GitHub, GitLab or Bitbucket."],
  [Braces, "An API", "Upload its OpenAPI or Swagger file."],
  [Bot, "A chatbot", "Your AI assistant's own endpoint."],
];

const steps = [
  ["Say what to test", "Paste an address, upload a file or link a repository. Nothing runs yet."],
  ["Choose what you want back", "A security audit, manual test cases, automation scripts, or all of them. Confirm you may test the app."],
  ["Read the results", "Findings ranked by severity with how to fix each, test cases to download, and what changed since the last scan."],
];

const everyDay: [LucideIcon, string, string][] = [
  [GitPullRequest, "On every pull request", "A scan of the branch, a comment on the pull request, and a pass or fail that only counts what the change added."],
  [CalendarClock, "On a timetable", "Daily, weekly or monthly, with a message in Slack or Teams saying what is new and what was fixed."],
  [Inbox, "One list of findings", "Mark each as fixed, accepted or not a problem, give it an owner, and the decision stays on later scans."],
  [ShieldCheck, "Mapped to OWASP", "Findings sorted under the OWASP Top 10, with a spreadsheet for whoever asks."],
];

/** A product screenshot in a plain window frame, with the same hard shadow the app's cards use. */
function Shot({ src, alt, className = "" }: { src: string; alt: string; className?: string }) {
  return (
    <figure className={`overflow-hidden rounded-2xl border-2 border-ink bg-white shadow-hard ${className}`}>
      <div className="flex items-center gap-1.5 border-b-2 border-ink bg-soft px-4 py-2.5" aria-hidden="true">
        <span className="h-2.5 w-2.5 rounded-full bg-brand-400" />
        <span className="h-2.5 w-2.5 rounded-full bg-brand-300" />
        <span className="h-2.5 w-2.5 rounded-full border border-ink" />
      </div>
      <img src={src} alt={alt} width={1280} height={800} loading="lazy" className="block h-auto w-full" />
    </figure>
  );
}

const wrap = "mx-auto w-full max-w-6xl px-5 md:px-8";
const primary = "inline-flex h-[52px] items-center gap-2 rounded-[10px] bg-brand-600 px-6 font-bold text-white hover:bg-brand-700";
const quiet = "inline-flex h-[52px] items-center rounded-[10px] border-[1.5px] border-ink bg-white px-6 font-semibold";

/** The public home page: what Wiseflow is, shown with the product's own screens. */
export function LandingPage() {
  const [free, setFree] = useState<string[]>([]);
  useEffect(() => {
    // The free plan's real limits, so this page never promises something the product does not give.
    getPlans().then((r) => setFree(r.data.plans[0]?.features ?? [])).catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-white font-sans text-ink">
      <header className={`${wrap} flex flex-wrap items-center justify-between gap-3 py-5`}>
        <Link to="/" aria-label="Wiseflow, home"><Logo /></Link>
        <nav aria-label="Main" className="flex flex-wrap items-center gap-1 sm:gap-2">
          <a href="#how" className="hidden min-h-[44px] items-center px-3 font-semibold sm:flex">How it works</a>
          <Link to="/guides" className="hidden min-h-[44px] items-center px-3 font-semibold sm:flex">Guides</Link>
          <Link to="/pricing" className="flex min-h-[44px] items-center px-3 font-semibold">Pricing</Link>
          <Link to="/login" className="flex min-h-[44px] items-center px-3 font-semibold">Sign in</Link>
          <Link to="/register" className="flex h-11 items-center rounded-[10px] bg-ink px-4 font-bold text-white">Start free</Link>
        </nav>
      </header>

      <main>
        <div className="relative overflow-hidden">
        <TechBackdrop />
        <section className={`${wrap} relative grid items-center gap-10 pb-16 pt-8 lg:grid-cols-[0.9fr_1.1fr] lg:pt-14`}>
          <div className="wf-fade-up flex flex-col items-start gap-6">
            <h1 className="text-[44px] font-extrabold leading-[1.05] tracking-tight sm:text-[58px]" style={{ textWrap: "balance" }}>
              Find what is broken before your customers do.
            </h1>
            <p className="max-w-[46ch] text-lg text-body">
              Point Wiseflow at a website, a mobile build, your code, an API or a chatbot. It looks for security problems, writes the test cases and automation scripts, and tells you what changed since last time.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link to="/register" className={primary}>Start free <ArrowRight className="h-[18px] w-[18px]" aria-hidden="true" /></Link>
              <a href="#how" className={quiet}>See how a scan goes</a>
            </div>
            {free.length > 0 && <p className="text-[15px] text-body">Free plan: {free.slice(0, 2).join(", ").toLowerCase()}. No card needed.</p>}
          </div>
          <Shot src="/landing/results.webp" alt="A finished Wiseflow scan: a risk score, the number of findings, and the findings to fix first" className="wf-fade-up" />
        </section>

        </div>

        <section className="border-y border-line bg-soft py-14">
          <div className={wrap}>
            <h2 className="text-3xl font-extrabold tracking-tight">Six things you can point it at</h2>
            <ul className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {targets.map(([Icon, name, about]) => (
                <li key={name} className="wf-lift flex items-start gap-4 rounded-2xl border border-gray-300 bg-white p-5">
                  <span className="flex h-12 w-12 flex-none items-center justify-center rounded-xl bg-brand-50 text-brand-700"><Icon className="h-6 w-6" aria-hidden="true" /></span>
                  <span>
                    <span className="block text-lg font-bold">{name}</span>
                    <span className="text-body">{about}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section id="how" className={`${wrap} scroll-mt-6 py-16`}>
          <h2 className="text-3xl font-extrabold tracking-tight">How a scan goes</h2>
          <ol className="mt-8 grid gap-6 md:grid-cols-3">
            {steps.map(([title, about], i) => (
              <li key={title} className="flex flex-col gap-2 border-t-[3px] border-ink pt-4">
                <span className="font-mono text-sm font-bold text-brand-700">Step {i + 1}</span>
                <h3 className="text-xl font-bold">{title}</h3>
                <p className="text-body">{about}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className={`${wrap} grid items-center gap-10 pb-16 lg:grid-cols-2`}>
          <Shot src="/landing/wise.webp" alt="Wise, the assistant, answering a question about a scan and linking to the finding it came from" />
          <div className="flex flex-col items-start gap-4">
            <WiseBot state="idle" className="h-20 w-20" />
            <h2 className="text-3xl font-extrabold tracking-tight">Ask Wise instead of digging</h2>
            <p className="max-w-[52ch] text-lg text-body">
              Wise answers from your own scans and the documents you give it, and links every answer to where it came from. Ask it to scan a site or set up a weekly check, and it does so once you confirm.
            </p>
            <ul className="flex flex-col gap-2">
              {["“What are my worst findings this month?”", "“Explain this one for my manager.”", "“Check https://shop.example.com every week.”"].map((q) => (
                <li key={q} className="flex items-start gap-2.5"><Check className="mt-1 h-[18px] w-[18px] flex-none text-brand-600" strokeWidth={3} aria-hidden="true" />{q}</li>
              ))}
            </ul>
          </div>
        </section>

        <section className="border-y border-line bg-soft py-16">
          <div className={`${wrap} grid items-center gap-10 lg:grid-cols-2`}>
            <div className="flex flex-col items-start gap-4">
              <h2 className="text-3xl font-extrabold tracking-tight">Test the AI you ship, too</h2>
              <p className="max-w-[52ch] text-lg text-body">
                Give Wiseflow your chatbot's address and it sends the messages an attacker would: instructions hidden in content, requests for another customer's details, attempts to get its hidden rules. You see each message, the reply, and whether it held.
              </p>
              <Link to="/register" className={quiet}>Test a chatbot</Link>
            </div>
            <Shot src="/landing/chatbot.webp" alt="A chatbot scan: two test messages the bot failed and one to check by hand, each with the bot's reply" />
          </div>
        </section>

        <section className={`${wrap} py-16`}>
          <h2 className="text-3xl font-extrabold tracking-tight">Built for every day, not once a quarter</h2>
          <ul className="mt-8 grid gap-x-10 gap-y-7 sm:grid-cols-2">
            {everyDay.map(([Icon, name, about]) => (
              <li key={name} className="flex items-start gap-4">
                <Icon className="mt-1 h-7 w-7 flex-none text-brand-600" aria-hidden="true" />
                <span>
                  <span className="block text-xl font-bold">{name}</span>
                  <span className="text-body">{about}</span>
                </span>
              </li>
            ))}
          </ul>
          <div className="mt-12 grid gap-6 rounded-2xl border border-gray-300 p-6 sm:grid-cols-3">
            {([[BranchCheck, "GitHub, GitLab, Bitbucket"], [Plugs, "Slack, Teams, Jira, Linear, Azure Boards"], [CompareSheets, "Claude, ChatGPT, Gemini, Grok with your own key"]] as const).map(([Art, text]) => (
              <div key={text} className="flex flex-col items-center gap-2 text-center">
                <Art className="h-24 w-auto" />
                <span className="font-semibold">{text}</span>
              </div>
            ))}
          </div>
        </section>

        <section aria-labelledby="faq" className="border-t border-line bg-soft py-16">
          <div className={`${wrap} grid gap-x-12 gap-y-6 lg:grid-cols-[0.7fr_1.3fr]`}>
            <div>
              <h2 id="faq" className="text-3xl font-extrabold tracking-tight">Questions people ask first</h2>
              <p className="mt-2 text-body">Short, plain answers. The <Link to="/pricing" className="font-semibold text-brand-600 underline">pricing page</Link> has the plans.</p>
            </div>
            <dl className="flex flex-col divide-y divide-line rounded-2xl border border-gray-300 bg-white">
              {faqs.map((f) => (
                <div key={f.q} className="px-6 py-5">
                  <dt className="text-lg font-bold">{f.q}</dt>
                  <dd className="mt-1.5 max-w-[68ch] text-body">{f.a}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        <section className="relative overflow-hidden bg-brand-700 py-14 text-white">
          <TechBackdrop variant="band" />
          <div className={`${wrap} relative flex flex-wrap items-center justify-between gap-6`}>
            <div>
              <h2 className="text-3xl font-extrabold tracking-tight">Run your first scan in a few minutes.</h2>
              <p className="mt-1 text-brand-100">Start on the free plan. Move to a team plan when you need more scans and people.</p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Link to="/register" className="inline-flex h-[52px] items-center rounded-[10px] bg-white px-6 font-bold text-brand-700">Start free</Link>
              <Link to="/pricing" className="inline-flex h-[52px] items-center rounded-[10px] border-[1.5px] border-white px-6 font-semibold">See pricing</Link>
            </div>
          </div>
        </section>
      </main>

      <footer className={`${wrap} flex flex-wrap items-center justify-between gap-4 py-8 text-[15px] text-body`}>
        <span>© {new Date().getFullYear()} Wiseflow</span>
        <nav aria-label="Footer" className="flex flex-wrap gap-x-5 gap-y-2">
          <Link to="/guides" className="font-semibold text-ink">Guides</Link>
          <Link to="/pricing" className="font-semibold text-ink">Pricing</Link>
          <Link to="/privacy" className="font-semibold text-ink">Privacy</Link>
          <Link to="/terms" className="font-semibold text-ink">Terms</Link>
          <Link to="/login" className="font-semibold text-ink">Sign in</Link>
        </nav>
      </footer>
    </div>
  );
}
