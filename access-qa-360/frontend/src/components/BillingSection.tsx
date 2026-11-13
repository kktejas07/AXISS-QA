import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { cancelBilling, getBilling, manageBilling, startCheckout } from "../api/billing";
import type { Billing } from "../api/billing";
import { apiError } from "../utils/errors";
import { errorBox, field, hint, label } from "./ui";

const planName: Record<string, string> = { individual: "Individual, free", team: "Team", enterprise: "Enterprise" };
const quiet = "h-11 rounded-[10px] border-[1.5px] border-gray-400 bg-white px-3.5 text-sm font-semibold disabled:opacity-50";

/** The organisation's plan, and for its owner the way to upgrade, manage or cancel. */
export function BillingSection() {
  const [params] = useSearchParams();
  const [billing, setBilling] = useState<Billing | null>(null);
  const [seats, setSeats] = useState(5);
  const [provider, setProvider] = useState<"stripe" | "razorpay">("stripe");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const returned = params.get("billing");

  useEffect(() => {
    getBilling()
      .then((r) => {
        setBilling(r.data);
        setSeats(Math.max(2, r.data.seats_used));
        if (!r.data.providers.stripe && r.data.providers.razorpay) setProvider("razorpay");
      })
      .catch(() => setError("The billing details could not be loaded."));
  }, []);

  /** Leave for the provider's page. The plan changes only once they confirm payment. */
  const go = async (action: () => Promise<{ data: { url: string } }>, fallback: string) => {
    setError("");
    setBusy(true);
    try {
      window.location.assign((await action()).data.url);
    } catch (e) {
      setError(apiError(e, fallback));
      setBusy(false);
    }
  };

  const cancel = async () => {
    setError("");
    setBusy(true);
    try {
      setBilling((await cancelBilling()).data);
    } catch (e) {
      setError(apiError(e, "The subscription could not be cancelled. Try again."));
    } finally {
      setBusy(false);
    }
  };

  const anyProvider = billing && (billing.providers.stripe || billing.providers.razorpay);
  const until = billing?.period_end ? new Date(billing.period_end).toLocaleDateString() : null;

  return (
    <section id="billing" className="scroll-mt-6 rounded-2xl border border-gray-300 bg-white p-6">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="text-lg font-bold">Plan and billing</h2>
        <Link to="/pricing" className="text-sm font-semibold text-brand-600">Compare plans</Link>
      </div>
      {error && <p role="alert" className={`${errorBox} mb-4`}>{error}</p>}
      {returned === "success" && billing && !billing.status && (
        <p role="status" className="mb-4 rounded-[10px] border border-emerald-200 bg-emerald-50 px-4 py-3 text-emerald-900">
          Thank you. Your payment is being confirmed; the Team plan switches on within a minute. Reload this page to see it.
        </p>
      )}
      {returned === "cancelled" && <p role="status" className="mb-4 rounded-[10px] border border-gray-300 bg-soft px-4 py-3">Checkout was closed before paying. Nothing was charged.</p>}

      {!billing ? null : (
        <div className="flex flex-col gap-5">
          <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-3">
            <div>
              <dt className="text-[13.5px] font-semibold text-body">Plan</dt>
              <dd className="text-xl font-bold">{planName[billing.account_type] ?? billing.account_type}</dd>
            </div>
            <div>
              <dt className="text-[13.5px] font-semibold text-body">Seats</dt>
              <dd className="text-xl font-bold">{billing.seat_limit === null ? `${billing.seats_used}, no limit` : `${billing.seats_used} of ${billing.seat_limit} used`}</dd>
            </div>
            {billing.status && (
              <div>
                <dt className="text-[13.5px] font-semibold text-body">Subscription</dt>
                <dd className={`text-xl font-bold ${billing.status === "active" ? "" : "text-red-700"}`}>
                  {billing.status === "active" ? (billing.cancel_at_period_end ? "Ending" : "Active") : billing.status === "past_due" ? "Payment failed" : "Ended"}
                </dd>
              </div>
            )}
          </dl>

          {billing.status === "active" && until && (
            <p className="text-body">{billing.cancel_at_period_end ? `Cancelled. Your team keeps the plan until ${until}, then scans stop until you renew.` : `Renews on ${until}.`}</p>
          )}
          {billing.status === "past_due" && <p role="alert" className={errorBox}>The last payment failed. Update the card to keep the Team plan; the provider will try again.</p>}
          {billing.status === "cancelled" && <p role="alert" className={errorBox}>The subscription has ended, so new scans cannot start. Results stay available. Subscribe again below to continue.</p>}

          {!billing.can_manage ? (
            <p className="text-body">Only the organisation's owner can change the plan.</p>
          ) : billing.status === "active" || billing.status === "past_due" ? (
            <div className="flex flex-wrap gap-2.5">
              {billing.provider === "stripe" && (
                <button type="button" disabled={busy} onClick={() => go(manageBilling, "The billing page could not be opened. Try again.")} className={quiet}>
                  Manage subscription
                </button>
              )}
              {billing.provider === "razorpay" && billing.status === "active" && !billing.cancel_at_period_end && (
                <button type="button" disabled={busy} onClick={cancel} className={quiet}>Cancel at the end of this period</button>
              )}
              {billing.provider === "stripe" && <span className={`${hint} self-center`}>Change the card, the number of seats, or cancel on Stripe's page.</span>}
            </div>
          ) : billing.account_type === "enterprise" ? (
            <p className="text-body">Enterprise accounts are invoiced. Contact Wiseflow to change yours.</p>
          ) : !anyProvider ? (
            <p className="text-body">Card payments are not switched on for this Wiseflow server. Contact Wiseflow to move to the Team plan.</p>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                go(() => startCheckout(provider, seats), "Checkout could not be started. Try again.");
              }}
              className="flex flex-col gap-4 border-t border-line pt-5"
            >
              <p className="font-semibold">{billing.status === "cancelled" ? "Subscribe again to start scans and keep your team's seats." : "Move to the Team plan to invite people and remove the monthly scan limit."}</p>
              <div className="flex flex-wrap items-end gap-4">
                <label className={`${label} w-32`}>
                  Seats
                  <input type="number" min={Math.max(1, billing.seats_used)} max={500} required value={seats} onChange={(e) => setSeats(Number(e.target.value))} className={field} />
                </label>
                {billing.providers.stripe && billing.providers.razorpay && (
                  <label className={`${label} min-w-0 flex-[0_1_260px]`}>
                    Pay in
                    <select value={provider} onChange={(e) => setProvider(e.target.value as "stripe" | "razorpay")} className={`${field} px-2.5`}>
                      <option value="stripe">US dollars, with Stripe</option>
                      <option value="razorpay">Indian rupees, with Razorpay</option>
                    </select>
                  </label>
                )}
                <button type="submit" disabled={busy} className="h-12 rounded-[10px] bg-brand-600 px-5 font-bold text-white hover:bg-brand-700 disabled:opacity-60">
                  {busy ? "Opening checkout" : "Continue to payment"}
                </button>
              </div>
              <span className={hint}>You pay on {provider === "stripe" ? "Stripe's" : "Razorpay's"} page. Wiseflow never sees your card. The plan switches on when the payment is confirmed.</span>
            </form>
          )}
        </div>
      )}
    </section>
  );
}
