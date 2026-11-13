import { Link, useParams } from "react-router-dom";
import { ArrowRight, Clock } from "lucide-react";
import { Logo } from "../components/Logo";
import { guide, guides } from "../content/guides";

const wrap = "mx-auto w-full max-w-6xl px-5 md:px-8";
const when = (date: string) => new Date(`${date}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });

function Frame({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-white font-sans text-ink">
      <header className={`${wrap} flex flex-wrap items-center justify-between gap-3 py-5`}>
        <Link to="/" aria-label="Wiseflow, home"><Logo /></Link>
        <nav aria-label="Main" className="flex flex-wrap items-center gap-x-6 gap-y-2 font-semibold">
          <Link to="/guides">Guides</Link>
          <Link to="/pricing">Pricing</Link>
          <Link to="/login">Sign in</Link>
          <Link to="/register" className="inline-flex h-11 items-center rounded-[10px] bg-ink px-4 font-bold text-white">Start free</Link>
        </nav>
      </header>
      <main className={`${wrap} pb-20 pt-6`}>{children}</main>
      <footer className={`${wrap} flex flex-wrap items-center justify-between gap-4 border-t border-line py-8 text-[15px] text-body`}>
        <span>© {new Date().getFullYear()} Wiseflow</span>
        <nav aria-label="Footer" className="flex flex-wrap gap-x-5 gap-y-2">
          <Link to="/" className="font-semibold text-ink">Home</Link>
          <Link to="/guides" className="font-semibold text-ink">Guides</Link>
          <Link to="/pricing" className="font-semibold text-ink">Pricing</Link>
        </nav>
      </footer>
    </div>
  );
}

/** The list of public guides. */
export function GuidesPage() {
  return (
    <Frame>
      <h1 className="text-[40px] font-extrabold leading-tight tracking-tight sm:text-5xl">Guides</h1>
      <p className="mt-3 max-w-[60ch] text-lg text-body">Short, practical explanations of testing and security topics, written to be useful whether or not you use Wiseflow.</p>
      <ul className="mt-10 grid gap-5 md:grid-cols-2">
        {guides.map((g) => (
          <li key={g.slug}>
            <Link to={`/guides/${g.slug}`} className="wf-lift flex h-full flex-col gap-2 rounded-2xl border-2 border-ink bg-white p-6 shadow-hard">
              <h2 className="text-xl font-bold">{g.title}</h2>
              <p className="text-body">{g.description}</p>
              <span className="mt-auto flex items-center gap-1.5 pt-2 text-sm font-semibold text-brand-600">
                Read the guide <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Frame>
  );
}

/** One guide. */
export function GuidePage({ slug: given }: { slug?: string }) {
  const params = useParams<{ slug: string }>();
  const g = guide(given ?? params.slug ?? "");
  if (!g) {
    return (
      <Frame>
        <h1 className="text-4xl font-extrabold tracking-tight">That guide does not exist</h1>
        <p className="mt-3 text-body">It may have been renamed. <Link to="/guides" className="font-semibold text-brand-600 underline">See all guides</Link>.</p>
      </Frame>
    );
  }
  return (
    <Frame>
      <article className="mx-auto max-w-[70ch]">
        <Link to="/guides" className="text-sm font-semibold text-brand-600 hover:text-brand-700">Guides</Link>
        <h1 className="mt-2 text-[36px] font-extrabold leading-[1.1] tracking-tight sm:text-[44px]" style={{ textWrap: "balance" }}>{g.title}</h1>
        <p className="mt-4 text-lg text-body">{g.description}</p>
        <p className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-[14.5px] text-body">
          <span className="flex items-center gap-1.5"><Clock className="h-4 w-4" aria-hidden="true" /> {g.minutes} minute read</span>
          <span>Updated <time dateTime={g.updated}>{when(g.updated)}</time></span>
        </p>
        {g.sections.map((s) => (
          <section key={s.heading} className="mt-10">
            <h2 className="text-2xl font-bold tracking-tight">{s.heading}</h2>
            {s.paragraphs?.map((p) => <p key={p} className="mt-3 text-[17px] leading-relaxed">{p}</p>)}
            {s.points && (
              <ul className="mt-3 flex flex-col gap-2.5 text-[17px] leading-relaxed">
                {s.points.map((p) => <li key={p} className="ml-5 list-disc">{p}</li>)}
              </ul>
            )}
          </section>
        ))}
        <aside className="mt-12 flex flex-wrap items-center justify-between gap-4 rounded-2xl border-2 border-ink bg-brand-100 p-6 shadow-hard">
          <p className="max-w-[40ch] text-lg font-bold">Try it on your own app. The free plan needs no card.</p>
          <Link to="/register" className="inline-flex h-12 items-center gap-2 rounded-[10px] bg-brand-600 px-5 font-bold text-white hover:bg-brand-700">
            Start free <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </aside>
      </article>
    </Frame>
  );
}
