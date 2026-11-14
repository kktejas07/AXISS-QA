import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowRight, Bot, Braces, Check, CheckCircle2, CircleSlash, Code2, Globe, Smartphone, XCircle } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { getStatus, sendContact } from "../api/public";
import type { ContactForm, ServiceStatus } from "../api/public";
import { PublicPage, wrap } from "../components/PublicSite";
import { TechBackdrop } from "../components/TechBackdrop";
import { card, errorBox, field, label, primaryButton, textarea } from "../components/ui";
import { WiseBot } from "../components/WiseBot";
import { changelog, product, products } from "../content/product";
import { apiError } from "../utils/errors";
import { topics } from "./HelpPage";

const icons: Record<string, LucideIcon> = { web: Globe, mobile: Smartphone, code: Code2, api: Braces, chatbot: Bot };
const h1 = "text-[40px] font-extrabold leading-[1.06] tracking-tight sm:text-[52px]";
const day = (date: string) => new Date(`${date}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });

function Shot({ src, alt }: { src: string; alt: string }) {
  return (
    <figure className="overflow-hidden rounded-2xl border-2 border-ink bg-white shadow-hard">
      <img src={src} alt={alt} width={1280} height={800} loading="lazy" className="block h-auto w-full" />
    </figure>
  );
}

function StartBand({ text = "Try it on your own app. The free plan needs no card." }: { text?: string }) {
  return (
    <section className="relative mt-20 overflow-hidden bg-brand-700 py-12 text-white">
      <TechBackdrop variant="band" />
      <div className={`${wrap} relative flex flex-wrap items-center justify-between gap-6`}>
        <p className="max-w-[32ch] text-2xl font-extrabold tracking-tight">{text}</p>
        <div className="flex flex-wrap gap-3">
          <Link to="/register" className="inline-flex h-[52px] items-center rounded-[10px] bg-white px-6 font-bold text-brand-700">Start free</Link>
          <Link to="/contact" className="inline-flex h-[52px] items-center rounded-[10px] border-[1.5px] border-white px-6 font-semibold">Contact sales</Link>
        </div>
      </div>
    </section>
  );
}

/** Everything Wiseflow scans, each leading to its own page. */
export function ProductsPage() {
  return (
    <PublicPage>
      <div className={`${wrap} pt-8`}>
        <h1 className={h1}>One tool, five things to point it at</h1>
        <p className="mt-4 max-w-[62ch] text-lg text-body">Each kind of scan gives you findings with how to fix them, test cases, and a report. Pick one to see exactly what it checks and where it stops.</p>
        <ul className="mt-10 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {products.map((p) => {
            const Icon = icons[p.slug];
            return (
              <li key={p.slug}>
                <Link to={`/product/${p.slug}`} className="wf-lift flex h-full flex-col gap-3 rounded-2xl border-2 border-ink bg-white p-6 shadow-hard">
                  <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand-100 text-brand-700"><Icon className="h-6 w-6" aria-hidden="true" /></span>
                  <h2 className="text-xl font-bold">{p.name}</h2>
                  <p className="text-body">{p.lead}</p>
                  <span className="mt-auto flex items-center gap-1.5 pt-1 text-sm font-semibold text-brand-600">What it checks <ArrowRight className="h-4 w-4" aria-hidden="true" /></span>
                </Link>
              </li>
            );
          })}
          <li>
            <Link to="/wise" className="wf-lift flex h-full flex-col gap-3 rounded-2xl border-2 border-ink bg-brand-100 p-6 shadow-hard">
              <WiseBot state="idle" className="h-12 w-12" />
              <h2 className="text-xl font-bold">Wise, the assistant</h2>
              <p className="text-body">Ask about your scans in plain words and get answers with their sources.</p>
              <span className="mt-auto flex items-center gap-1.5 pt-1 text-sm font-semibold text-brand-700">Meet Wise <ArrowRight className="h-4 w-4" aria-hidden="true" /></span>
            </Link>
          </li>
        </ul>
      </div>
      <StartBand />
    </PublicPage>
  );
}

function Ticks({ items }: { items: string[] }) {
  return (
    <ul className="mt-4 flex flex-col gap-3">
      {items.map((t) => (
        <li key={t} className="flex items-start gap-3">
          <Check className="mt-0.5 h-5 w-5 flex-none text-brand-600" strokeWidth={2.6} aria-hidden="true" />
          <span>{t}</span>
        </li>
      ))}
    </ul>
  );
}

/** One kind of scan: what you give it, what it finds, what you get, and what it does not do. */
export function ProductPage({ slug: given }: { slug?: string }) {
  const params = useParams<{ slug: string }>();
  const p = product(given ?? params.slug ?? "");
  if (!p) {
    return (
      <PublicPage>
        <div className={`${wrap} py-10`}>
          <h1 className="text-4xl font-extrabold tracking-tight">That page does not exist</h1>
          <p className="mt-3 text-body"><Link to="/product" className="font-semibold text-brand-600 underline">See everything Wiseflow scans</Link>.</p>
        </div>
      </PublicPage>
    );
  }
  const Icon = icons[p.slug];
  return (
    <PublicPage>
      <div className={`${wrap} grid items-center gap-10 pt-8 ${p.shot ? "lg:grid-cols-[0.95fr_1.05fr]" : ""}`}>
        <div>
          <Link to="/product" className="text-sm font-semibold text-brand-600 hover:text-brand-700">Product</Link>
          <span className="mt-3 flex h-14 w-14 items-center justify-center rounded-2xl border-2 border-ink bg-brand-100 text-brand-700 shadow-hard"><Icon className="h-7 w-7" aria-hidden="true" /></span>
          <h1 className={`${h1} mt-5`} style={{ textWrap: "balance" }}>{p.title}</h1>
          <p className="mt-4 max-w-[58ch] text-lg text-body">{p.lead}</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link to="/register" className="inline-flex h-[52px] items-center gap-2 rounded-[10px] bg-brand-600 px-6 font-bold text-white hover:bg-brand-700">Start free <ArrowRight className="h-[18px] w-[18px]" aria-hidden="true" /></Link>
            <Link to="/pricing" className="inline-flex h-[52px] items-center rounded-[10px] border-[1.5px] border-ink bg-white px-6 font-semibold">See pricing</Link>
          </div>
        </div>
        {p.shot && <Shot {...p.shot} />}
      </div>
      <div className={`${wrap} mt-16 grid gap-6 lg:grid-cols-2`}>
        <section className={`${card} p-7`}>
          <h2 className="text-2xl font-bold tracking-tight">What it looks for</h2>
          <Ticks items={p.finds} />
        </section>
        <section className={`${card} p-7`}>
          <h2 className="text-2xl font-bold tracking-tight">What you get back</h2>
          <Ticks items={p.gives} />
        </section>
        <section className={`${card} p-7`}>
          <h2 className="text-2xl font-bold tracking-tight">What you give it</h2>
          <p className="mt-3 text-body">{p.input}</p>
        </section>
        <section className="rounded-2xl border-2 border-ink bg-soft p-7">
          <h2 className="text-2xl font-bold tracking-tight">Where it stops</h2>
          <p className="mt-3">{p.limits}</p>
        </section>
      </div>
      <div className={`${wrap} mt-14`}>
        <h2 className="text-xl font-bold">Other things Wiseflow scans</h2>
        <ul className="mt-4 flex flex-wrap gap-3">
          {products.filter((o) => o.slug !== p.slug).map((o) => (
            <li key={o.slug}><Link to={`/product/${o.slug}`} className="inline-flex min-h-[44px] items-center rounded-full border-[1.5px] border-ink px-4 font-semibold hover:bg-soft">{o.name}</Link></li>
          ))}
        </ul>
      </div>
      <StartBand />
    </PublicPage>
  );
}

const wiseDoes: [string, string, "searching" | "thinking" | "working" | "reading"][] = [
  ["Answers from your own scans", "Ask what your worst findings are, what changed since last week, or how to fix one. Wise reads your scans, not the internet, and links every answer to the scan it came from.", "searching"],
  ["Knows your product", "Give it requirements or user stories and its answers are about your product. Documents stay inside your organisation.", "reading"],
  ["Does things, after you say yes", "Ask it to scan a site or check it every week. It shows what it is about to do and waits for you to confirm.", "working"],
  ["Uses the AI you choose", "Claude by default. Your organisation can bring its own key for Claude, ChatGPT, Gemini, Grok, Mistral, DeepSeek, Groq or OpenRouter.", "thinking"],
];

/** Wise, the assistant: what it does, shown with the owl in the state that matches. */
export function WisePage() {
  return (
    <PublicPage>
      <div className={`${wrap} grid items-center gap-10 pt-8 lg:grid-cols-[1fr_1fr]`}>
        <div>
          <WiseBot state="listening" className="h-24 w-24" />
          <h1 className={`${h1} mt-5`}>Ask Wise instead of digging</h1>
          <p className="mt-4 max-w-[56ch] text-lg text-body">Wise is the assistant inside Wiseflow. It answers questions about your scans in plain words, shows where each answer came from, and can start a scan or a schedule for you.</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link to="/register" className="inline-flex h-[52px] items-center gap-2 rounded-[10px] bg-brand-600 px-6 font-bold text-white hover:bg-brand-700">Start free <ArrowRight className="h-[18px] w-[18px]" aria-hidden="true" /></Link>
          </div>
        </div>
        <Shot src="/landing/wise.webp" alt="Wise, the assistant, answering a question about a scan and listing the findings it used" />
      </div>
      <ul className={`${wrap} mt-16 grid gap-6 md:grid-cols-2`}>
        {wiseDoes.map(([title, about, mood]) => (
          <li key={title} className={`${card} flex items-start gap-5 p-6`}>
            <WiseBot state={mood} className="h-16 w-16" />
            <div>
              <h2 className="text-xl font-bold">{title}</h2>
              <p className="mt-1.5 text-body">{about}</p>
            </div>
          </li>
        ))}
      </ul>
      <section className={`${wrap} mt-14`}>
        <h2 className="text-2xl font-bold tracking-tight">Where it stops</h2>
        <p className="mt-3 max-w-[70ch]">Wise answers from what is in your scans and documents. If the answer is not there, it says so rather than guessing. It never starts a scan, changes a schedule or sends anything without your confirmation.</p>
      </section>
      <StartBand text="Ask Wise about your first scan in a few minutes." />
    </PublicPage>
  );
}

/** The help topics, readable without signing in. */
export function DocsPage() {
  return (
    <PublicPage>
      <div className={`${wrap} pt-8`}>
        <h1 className={h1}>Docs</h1>
        <p className="mt-4 max-w-[60ch] text-lg text-body">How to do the common things in Wiseflow. Links into the app ask you to sign in first.</p>
        <div className="mt-10 flex flex-wrap items-start gap-8 pb-4">
          <nav aria-label="Docs topics" className={`${card} flex-[1_1_220px] p-4 lg:sticky lg:top-6 lg:max-w-[270px]`}>
            <ul className="flex flex-col">
              {topics.map((t) => <li key={t.id}><a href={`#${t.id}`} className="block rounded-lg px-3 py-2 text-[15px] font-medium text-body hover:bg-soft hover:text-ink">{t.title}</a></li>)}
            </ul>
          </nav>
          <div className="flex min-w-0 flex-[999_1_480px] flex-col gap-5">
            {topics.map((t) => (
              <section key={t.id} id={t.id} aria-labelledby={`${t.id}-title`} className={`${card} scroll-mt-6 p-6`}>
                <h2 id={`${t.id}-title`} className="mb-2 text-xl font-bold">{t.title}</h2>
                <div className="flex max-w-[68ch] flex-col gap-3 text-[16px] leading-relaxed [&_a]:font-semibold [&_a]:text-brand-600 [&_a]:underline [&_code]:font-mono [&_code]:text-[13.5px] [&_li]:ml-5 [&_li]:list-disc [&_pre]:overflow-x-auto [&_pre]:rounded-[10px] [&_pre]:bg-ink [&_pre]:p-4 [&_pre]:text-white [&_ul]:flex [&_ul]:flex-col [&_ul]:gap-1.5">{t.body}</div>
              </section>
            ))}
          </div>
        </div>
      </div>
      <StartBand />
    </PublicPage>
  );
}

/** What shipped, newest first. */
export function ChangelogPage() {
  return (
    <PublicPage>
      <div className={`${wrap} pb-20 pt-8`}>
        <h1 className={h1}>Changelog</h1>
        <p className="mt-4 max-w-[60ch] text-lg text-body">What has changed in Wiseflow, newest first.</p>
        <ol className="mt-10 flex flex-col gap-6">
          {changelog.map((entry) => (
            <li key={entry.title} className="grid gap-x-8 gap-y-2 md:grid-cols-[180px_1fr]">
              <time dateTime={entry.date} className="pt-6 font-mono text-sm font-semibold text-brand-700">{day(entry.date)}</time>
              <article className={`${card} p-6`}>
                <h2 className="text-xl font-bold">{entry.title}</h2>
                <ul className="mt-3 flex flex-col gap-2">
                  {entry.items.map((i) => <li key={i} className="ml-5 list-disc text-body">{i}</li>)}
                </ul>
              </article>
            </li>
          ))}
        </ol>
      </div>
    </PublicPage>
  );
}

const asks: [ContactForm["kind"], string][] = [["demo", "A demo"], ["pricing", "A price for my team"], ["enterprise", "Enterprise terms"], ["other", "Something else"]];

/** Contact sales. The message goes to the Wiseflow team; nothing is sent anywhere else. */
export function ContactPage() {
  const [form, setForm] = useState<ContactForm>({ name: "", email: "", company: "", kind: "demo", message: "", website: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);
  const set = (key: keyof ContactForm) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setForm({ ...form, [key]: e.target.value });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await sendContact({ ...form, company: form.company?.trim() || undefined });
      setSent(true);
    } catch (err) {
      setError(apiError(err, "Your message could not be sent. Check your connection and try again."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <PublicPage>
      <div className={`${wrap} grid gap-x-14 gap-y-8 pb-20 pt-8 lg:grid-cols-[0.85fr_1.15fr]`}>
        <div>
          <h1 className={h1}>Talk to us</h1>
          <p className="mt-4 max-w-[46ch] text-lg text-body">Ask for a demo on your own app, a price for your team, or Enterprise terms. A person reads every message.</p>
          <ul className="mt-6 flex flex-col gap-3">
            {["See a scan of your own site, app or chatbot", "A price for the number of people you have", "Invoicing, limits and terms for larger organisations"].map((t) => (
              <li key={t} className="flex items-start gap-3"><Check className="mt-0.5 h-5 w-5 flex-none text-brand-600" strokeWidth={2.6} aria-hidden="true" />{t}</li>
            ))}
          </ul>
          <p className="mt-6 text-body">Prefer to look first? <Link to="/register" className="font-semibold text-brand-600 underline">Start on the free plan</Link>; it needs no card.</p>
        </div>
        {sent ? (
          <div role="status" className="self-start rounded-2xl border-2 border-ink bg-white p-8 shadow-hard">
            <WiseBot state="done" className="h-20 w-20" />
            <h2 className="mt-4 text-2xl font-bold">Thank you. Your message is with us.</h2>
            <p className="mt-2 text-body">We will reply to {form.email}.</p>
          </div>
        ) : (
          <form onSubmit={submit} className="flex flex-col gap-4 rounded-2xl border-2 border-ink bg-white p-7 shadow-hard">
            <div className="grid gap-4 sm:grid-cols-2">
              <label className={label}>Your name<input required maxLength={120} autoComplete="name" value={form.name} onChange={set("name")} className={field} /></label>
              <label className={label}>Work email<input required type="email" autoComplete="email" value={form.email} onChange={set("email")} className={field} /></label>
              <label className={label}>Company (optional)<input maxLength={160} autoComplete="organization" value={form.company} onChange={set("company")} className={field} /></label>
              <label className={label}>What you are asking for
                <select value={form.kind} onChange={set("kind")} className={`${field} px-2.5`}>{asks.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select>
              </label>
            </div>
            <label className={label}>Message<textarea required minLength={10} maxLength={4000} rows={6} value={form.message} onChange={set("message")} placeholder="What you would like to test, and how many people would use it." className={textarea} /></label>
            {/* Not for people: left empty by anyone who can see the page. */}
            <div aria-hidden="true" className="absolute -left-[9999px] h-0 w-0 overflow-hidden"><label>Website<input tabIndex={-1} autoComplete="off" value={form.website} onChange={set("website")} /></label></div>
            {error && <p role="alert" className={errorBox}>{error}</p>}
            <button type="submit" disabled={busy} className={`${primaryButton} self-start`}>{busy ? "Sending" : "Send message"}</button>
          </form>
        )}
      </div>
    </PublicPage>
  );
}

/** Is Wiseflow up right now? Asks the server each time the page is opened. */
export function StatusPage() {
  const [status, setStatus] = useState<ServiceStatus | null | "down">(null);
  useEffect(() => {
    getStatus().then((r) => setStatus(r.data)).catch(() => setStatus("down"));
  }, []);
  const down = status === "down";
  const parts = down ? [{ name: "Website and API", ok: false }, { name: "Database", ok: false }] : status?.parts ?? [];
  const ok = !down && !!status?.ok;
  return (
    <PublicPage>
      <div className={`${wrap} pb-20 pt-8`}>
        <h1 className={h1}>Status</h1>
        {status === null ? (
          <p role="status" className="mt-8 flex items-center gap-3 text-lg text-body"><CircleSlash className="h-6 w-6" aria-hidden="true" /> Checking</p>
        ) : (
          <>
            <p role="status" className={`mt-8 flex items-center gap-3 rounded-2xl border-2 px-6 py-5 text-xl font-bold ${ok ? "border-emerald-700 bg-emerald-50 text-emerald-900" : "border-red-700 bg-red-50 text-red-800"}`}>
              {ok ? <CheckCircle2 className="h-7 w-7" aria-hidden="true" /> : <XCircle className="h-7 w-7" aria-hidden="true" />}
              {ok ? "Wiseflow is up." : down ? "Wiseflow's server cannot be reached right now." : "Part of Wiseflow is down."}
            </p>
            <ul className={`${card} mt-6 max-w-2xl`}>
              {parts.map((part, i) => (
                <li key={part.name} className={`flex items-center justify-between gap-4 px-5 py-4 ${i ? "border-t border-line" : ""}`}>
                  <span className="font-semibold">{part.name}</span>
                  <span className={`rounded-full px-2.5 py-1 text-[13px] font-bold ${part.ok ? "bg-emerald-100 text-emerald-900" : "bg-red-100 text-red-800"}`}>{part.ok ? "Working" : "Down"}</span>
                </li>
              ))}
            </ul>
            {!down && status && <p className="mt-4 text-[14.5px] text-body">Checked {new Date(status.checked_at).toLocaleTimeString()}. Reload the page to check again.</p>}
          </>
        )}
      </div>
    </PublicPage>
  );
}
