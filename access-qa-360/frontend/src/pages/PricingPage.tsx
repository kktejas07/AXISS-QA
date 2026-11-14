import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bot, Braces, Check, Code2, GitBranch, Globe, Smartphone } from "lucide-react";
import { Faq } from "../components/Faq";
import { PublicFooter, PublicHeader } from "../components/PublicSite";
import { TechBackdrop } from "../components/TechBackdrop";
import { fallbackPlans, pricingFaqs } from "../content/site";
import { getPlans } from "../api/billing";
import type { Plan } from "../api/billing";

type Currency = "usd" | "inr";

function price(plan: Plan, currency: Currency): string {
  const amount = currency === "usd" ? plan.price_usd : plan.price_inr;
  if (amount === undefined) return "Per person";          // the price is the server's to say, and it has not answered
  if (amount === null) return "Talk to us";
  if (amount === 0) return "Free";
  return currency === "usd" ? `$${amount}` : `₹${amount.toLocaleString("en-IN")}`;
}

/** What a team of a given size pays. Only shown once the server has said the price. */
function Calculator({ plans, currency }: { plans: Plan[]; currency: Currency }) {
  const [people, setPeople] = useState(5);
  const team = plans.find((p) => p.id === "team");
  const each = team && (currency === "usd" ? team.price_usd : team.price_inr);
  if (!each) return null;
  const show = (n: number) => (currency === "usd" ? `$${n.toLocaleString("en-US")}` : `₹${n.toLocaleString("en-IN")}`);
  return (
    <section aria-labelledby="calculator" className="mx-auto mt-14 max-w-6xl px-4 md:px-8">
      <div className="grid gap-x-10 gap-y-6 rounded-2xl border-2 border-ink bg-white p-7 shadow-hard lg:grid-cols-[1.1fr_0.9fr]">
        <div>
          <h2 id="calculator" className="text-2xl font-extrabold tracking-tight">What would your team pay?</h2>
          <p className="mt-1 text-body">Team is priced per person. Scans are not counted or charged, however many you run.</p>
          <label htmlFor="people" className="mt-5 block text-sm font-semibold">People on the team: {people}</label>
          <input id="people" type="range" min={2} max={100} value={people} onChange={(e) => setPeople(Number(e.target.value))} className="mt-2 h-11 w-full accent-brand-600" />
          <div className="flex justify-between text-[13px] text-body"><span>2</span><span>100</span></div>
        </div>
        <dl className="grid grid-cols-2 gap-4 self-center">
          <div className="rounded-xl bg-soft p-5">
            <dt className="text-sm font-semibold text-body">Each month</dt>
            <dd className="text-[34px] font-extrabold leading-tight tracking-tight">{show(each * people)}</dd>
          </div>
          <div className="rounded-xl bg-soft p-5">
            <dt className="text-sm font-semibold text-body">Each year</dt>
            <dd className="text-[34px] font-extrabold leading-tight tracking-tight">{show(each * people * 12)}</dd>
          </div>
          <p className="col-span-2 text-[14px] text-body">{show(each)} per person, per month, billed monthly. Taxes may be added. More than 100 people? <Link to="/contact" className="font-semibold text-brand-600 underline">Talk to us</Link>.</p>
        </dl>
      </div>
    </section>
  );
}

/** Public pricing page. Prices come from the server's settings. */
export function PricingPage() {
  // Shown at once from the built-in copy, then replaced by the server's answer, which has the prices.
  const [plans, setPlans] = useState<Plan[]>(fallbackPlans);
  const [salesEmail, setSalesEmail] = useState<string | null>(null);
  const [currency, setCurrency] = useState<Currency>("usd");
  const signedIn = typeof localStorage !== "undefined" && !!localStorage.getItem("token");

  useEffect(() => {
    getPlans()
      .then((r) => {
        setPlans(r.data.plans);
        setSalesEmail(r.data.sales_email);
        // Rupees first when only the Indian provider is switched on.
        if (r.data.providers.razorpay && !r.data.providers.stripe) setCurrency("inr");
      })
      .catch(() => {});          // the built-in copy stays; only the Team price is missing
  }, []);

  return (
    <div className="min-h-screen bg-white font-sans text-ink">
      <PublicHeader />

      <main className="pb-20">
        <div className="relative overflow-hidden">
        <TechBackdrop variant="band-light" />
        <div className="relative mx-auto max-w-6xl px-4 pt-10 md:px-8">
        <h1 className="max-w-3xl text-[44px] font-extrabold leading-[1.05] tracking-tight md:text-[56px]">Start free. Pay when your team joins.</h1>
        <p className="mt-4 max-w-2xl text-lg text-body">Every plan runs every kind of scan and gives you the report, test cases and scripts to download. Plans differ in how many people and how many scans.</p>

        <div role="group" aria-label="Currency" className="mt-8 inline-flex gap-1.5 rounded-xl border border-line bg-soft p-1">
          {(["usd", "inr"] as const).map((c) => (
            <button key={c} type="button" aria-pressed={currency === c} onClick={() => setCurrency(c)} className={`min-h-[44px] rounded-[9px] px-4 text-sm font-semibold ${currency === c ? "bg-ink text-white" : "text-ink"}`}>
              {c === "usd" ? "US dollars" : "Indian rupees"}
            </button>
          ))}
        </div>

        <div className="mt-8 grid gap-5 lg:grid-cols-3">
            {plans.map((plan) => {
              const featured = plan.id === "team";
              return (
                <section key={plan.id} aria-label={plan.name} className={`flex flex-col gap-5 rounded-2xl bg-white p-7 ${featured ? "border-2 border-ink shadow-hard" : "border border-gray-300"}`}>
                  <div>
                    <h2 className="text-xl font-bold">{plan.name}</h2>
                    <p className="mt-1 text-body">{plan.summary}</p>
                  </div>
                  <p>
                    <span className="text-[44px] font-extrabold leading-none tracking-tight">{price(plan, currency)}</span>
                    {plan.per && <span className="mt-1 block text-[14.5px] text-body">{plan.per}</span>}
                  </p>
                  <ul className="flex flex-1 flex-col gap-2.5">
                    {plan.features.map((f) => (
                      <li key={f} className="flex items-start gap-2.5">
                        <Check className="mt-0.5 h-[18px] w-[18px] flex-none text-brand-600" strokeWidth={2.8} aria-hidden="true" />
                        {f}
                      </li>
                    ))}
                  </ul>
                  {plan.id === "enterprise" ? (
                    salesEmail ? (
                      <p className="rounded-[10px] bg-soft px-4 py-3 text-[14.5px]">
                        Write to <span className="break-all font-semibold">{salesEmail}</span> and we will set it up with you.
                      </p>
                    ) : (
                      <Link to="/contact" className="flex h-[52px] items-center justify-center rounded-[10px] border-[1.5px] border-ink bg-white font-bold">Contact sales</Link>
                    )
                  ) : (
                    <Link
                      to={signedIn ? (plan.id === "team" ? "/settings#billing" : "/") : "/register"}
                      className={`flex h-[52px] items-center justify-center rounded-[10px] font-bold ${featured ? "bg-brand-600 text-white hover:bg-brand-700" : "border-[1.5px] border-ink bg-white"}`}
                    >
                      {plan.id === "team" ? (signedIn ? "Upgrade in Settings" : "Start free, upgrade later") : signedIn ? "Open the app" : "Start free"}
                    </Link>
                  )}
                </section>
              );
            })}
        </div>
        <p className="mt-6 max-w-2xl text-[14.5px] text-body">Team is billed monthly by card and can be cancelled at any time; it stays active until the end of the month already paid for. Taxes may be added at checkout.</p>
        </div>
        </div>

        <Calculator plans={plans} currency={currency} />

        <section aria-labelledby="included" className="mt-16 border-y border-line bg-soft py-14">
          <div className="mx-auto max-w-6xl px-4 md:px-8">
            <h2 id="included" className="text-3xl font-extrabold tracking-tight">On every plan, including the free one</h2>
            <ul className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {([[Globe, "Website scans", "Pages behind a login too, with accessibility and speed."], [Smartphone, "Mobile build scans", "Android .apk and iOS .ipa files."], [Code2, "Source code scans", "Secrets, risky code and vulnerable packages."],
                 [GitBranch, "Repository scans", "GitHub, GitLab or Bitbucket, and every pull request."], [Braces, "API scans", "From an OpenAPI or Swagger file."], [Bot, "Chatbot scans", "The messages an attacker would send your AI assistant."]] as const).map(([Icon, name, about]) => (
                <li key={name} className="flex items-start gap-4 rounded-2xl border border-gray-300 bg-white p-5">
                  <span className="flex h-11 w-11 flex-none items-center justify-center rounded-xl bg-brand-100 text-brand-700"><Icon className="h-5 w-5" aria-hidden="true" /></span>
                  <span>
                    <span className="block font-bold">{name}</span>
                    <span className="text-[15px] text-body">{about}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section aria-labelledby="pricing-faq" className="mx-auto mt-16 grid max-w-6xl gap-x-12 gap-y-6 px-4 md:px-8 lg:grid-cols-[0.7fr_1.3fr]">
          <div>
            <h2 id="pricing-faq" className="text-3xl font-extrabold tracking-tight">Questions about paying</h2>
            <p className="mt-2 text-body">Anything else, ask Wise once you are signed in.</p>
          </div>
          <Faq items={pricingFaqs} />
        </section>
      </main>
      <PublicFooter />
    </div>
  );
}
