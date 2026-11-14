import { Link } from "react-router-dom";
import { Logo } from "./Logo";
import { products } from "../content/product";

export const wrap = "mx-auto w-full max-w-6xl px-5 md:px-8";
const signedIn = () => typeof localStorage !== "undefined" && !!localStorage.getItem("token");
const item = "flex min-h-[44px] items-center px-3 font-semibold";

/** The menu at the top of every public page. */
export function PublicHeader() {
  return (
    <header className={`${wrap} flex flex-wrap items-center justify-between gap-x-3 gap-y-1 py-5`}>
      <Link to="/" aria-label="Wiseflow, home"><Logo /></Link>
      <nav aria-label="Main" className="flex flex-wrap items-center gap-x-1 sm:gap-x-2">
        <Link to="/product" className={`hidden md:flex ${item}`}>Product</Link>
        <Link to="/wise" className={`hidden lg:flex ${item}`}>Wise</Link>
        <Link to="/guides" className={`hidden sm:flex ${item}`}>Guides</Link>
        <Link to="/docs" className={`hidden lg:flex ${item}`}>Docs</Link>
        <Link to="/pricing" className={item}>Pricing</Link>
        {signedIn() ? (
          <Link to="/" className="flex h-11 items-center rounded-[10px] bg-ink px-4 font-bold text-white">Open the app</Link>
        ) : (
          <>
            <Link to="/login" className={item}>Sign in</Link>
            <Link to="/register" className="flex h-11 items-center rounded-[10px] bg-ink px-4 font-bold text-white">Start free</Link>
          </>
        )}
      </nav>
    </header>
  );
}

const columns: [string, [string, string][]][] = [
  ["Product", [...products.map((p): [string, string] => [p.name, `/product/${p.slug}`]), ["Wise, the assistant", "/wise"], ["Pricing", "/pricing"]]],
  ["Resources", [["Guides", "/guides"], ["Docs", "/docs"], ["Changelog", "/changelog"], ["Status", "/status"]]],
  ["Company", [["Contact sales", "/contact"], ["Sign in", "/login"], ["Start free", "/register"]]],
  ["Legal", [["Privacy", "/privacy"], ["Terms", "/terms"]]],
];

/** The footer of every public page: every public page is one click from here. */
export function PublicFooter() {
  return (
    <footer className="border-t border-line bg-soft">
      <div className={`${wrap} grid gap-x-8 gap-y-10 py-12 sm:grid-cols-2 lg:grid-cols-[1.2fr_repeat(4,1fr)]`}>
        <div>
          <Logo />
          <p className="mt-3 max-w-[30ch] text-[15px] text-body">AI testing and security checks for websites, mobile apps, code, APIs and chatbots.</p>
        </div>
        {columns.map(([title, links]) => (
          <nav key={title} aria-label={title}>
            <h2 className="text-sm font-bold">{title}</h2>
            <ul className="mt-3 flex flex-col gap-2.5 text-[15px]">
              {links.map(([name, to]) => <li key={to}><Link to={to} className="text-body hover:text-ink hover:underline">{name}</Link></li>)}
            </ul>
          </nav>
        ))}
      </div>
      <p className={`${wrap} border-t border-line py-5 text-[14px] text-body`}>© {new Date().getFullYear()} Wiseflow</p>
    </footer>
  );
}

/** A public page: the shared menu, the page's own content, and the shared footer. */
export function PublicPage({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-white font-sans text-ink">
      <PublicHeader />
      <main className="flex-1">{children}</main>
      <PublicFooter />
    </div>
  );
}
