import client from "./client";
import type {
  BillingConfig,
  CheckoutResponse,
  Plan,
  PlanTier,
  PortalResponse,
  SubscriptionResponse,
  UsageSummary,
} from "./types";

// Usage totals for the current billing month (API-key auth via X-API-Key).
export async function getUsage(): Promise<UsageSummary> {
  const { data } = await client.get<UsageSummary>("/usage");
  return data;
}

export async function getPlans(): Promise<Plan[]> {
  const { data } = await client.get<Plan[]>("/plans");
  return data;
}

export async function getSubscription(): Promise<SubscriptionResponse> {
  const { data } = await client.get<SubscriptionResponse>("/subscription");
  return data;
}

export async function getBillingConfig(): Promise<BillingConfig> {
  const { data } = await client.get<BillingConfig>("/billing/config");
  return data;
}

export async function createCheckout(planTier: PlanTier): Promise<CheckoutResponse> {
  const { data } = await client.post<CheckoutResponse>("/billing/checkout", {
    plan_tier: planTier,
  });
  return data;
}

export async function openBillingPortal(): Promise<PortalResponse> {
  const { data } = await client.post<PortalResponse>("/billing/portal", {});
  return data;
}
