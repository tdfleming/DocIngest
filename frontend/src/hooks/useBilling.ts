import { useQuery } from "@tanstack/react-query";
import {
  getBillingConfig,
  getPlans,
  getSubscription,
  getUsage,
} from "../api/billing";

// Usage requires an API key; the query is only enabled once one is configured.
export function useUsage(enabled: boolean) {
  return useQuery({
    queryKey: ["usage"],
    queryFn: getUsage,
    enabled,
    refetchInterval: 30_000,
  });
}

export function usePlans() {
  return useQuery({ queryKey: ["plans"], queryFn: getPlans });
}

// Subscription resolves per-org from the JWT; 403 when the token carries no org
// (legacy single-tenant), which the page surfaces as a friendly notice.
export function useSubscription() {
  return useQuery({
    queryKey: ["subscription"],
    queryFn: getSubscription,
    retry: false,
  });
}

export function useBillingConfig() {
  return useQuery({ queryKey: ["billingConfig"], queryFn: getBillingConfig });
}
