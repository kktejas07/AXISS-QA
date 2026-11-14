import api from "./client";

export interface Plan {
  id: "individual" | "team" | "enterprise";
  name: string;
  /** Whole US dollars; null means "ask us". */
  /** Left out when the price is not known yet (the server has not answered). */
  price_usd?: number | null;
  price_inr?: number | null;
  per: string | null;
  summary: string;
  features: string[];
}

export interface Billing {
  account_type: string;
  seat_limit: number | null;
  seats_used: number;
  provider: "stripe" | "razorpay" | null;
  status: "active" | "past_due" | "cancelled" | null;
  seats: number | null;
  period_end: string | null;
  cancel_at_period_end: boolean;
  providers: { stripe: boolean; razorpay: boolean };
  can_manage: boolean;
}

export const getPlans = () => api.get<{ plans: Plan[]; providers: { stripe: boolean; razorpay: boolean }; sales_email: string | null }>("/billing/plans");
export const getBilling = () => api.get<Billing>("/billing");
/** Returns the address of the provider's payment page. */
export const startCheckout = (provider: "stripe" | "razorpay", seats: number) => api.post<{ url: string }>("/billing/checkout", { provider, seats });
export const manageBilling = () => api.post<{ url: string }>("/billing/manage");
export const cancelBilling = () => api.post<Billing>("/billing/cancel");
