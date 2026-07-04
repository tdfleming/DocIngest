import {
  Alert,
  AlertIcon,
  Box,
  Heading,
  Spinner,
  VStack,
} from "@chakra-ui/react";
import { Link } from "react-router-dom";
import { useApiKey } from "../contexts/ApiKeyContext";
import {
  useBillingConfig,
  usePlans,
  useSubscription,
  useUsage,
} from "../hooks/useBilling";
import UsageMeters from "../components/billing/UsageMeters";
import CurrentPlanCard from "../components/billing/CurrentPlanCard";
import PlanCards from "../components/billing/PlanCards";

export default function BillingPage() {
  const { isSet } = useApiKey();
  const subscription = useSubscription();
  const plans = usePlans();
  const usage = useUsage(isSet);
  const billingConfig = useBillingConfig();

  if (subscription.isLoading || plans.isLoading) {
    return <Spinner />;
  }

  // No org on the JWT (legacy single-tenant) → subscription 403s. Fall back to the
  // FREE plan from the catalog so usage still renders against sensible limits.
  const hasOrg = !subscription.isError && !!subscription.data;
  const currentPlan =
    subscription.data?.plan ?? plans.data?.find((p) => p.tier === "free");
  const billingEnabled = (billingConfig.data?.enabled ?? false) && hasOrg;

  return (
    <VStack align="stretch" spacing={6}>
      {!hasOrg && (
        <Alert status="info" borderRadius="md">
          <AlertIcon />
          This account isn't linked to an organization, so plan changes and billing
          aren't available. Usage below reflects the free-tier limits.
        </Alert>
      )}

      {hasOrg && subscription.data && (
        <CurrentPlanCard
          subscription={subscription.data}
          billingEnabled={billingEnabled}
        />
      )}

      {!isSet ? (
        <Alert status="warning" borderRadius="md">
          <AlertIcon />
          No API key configured.
          <Link to="/config" className="ml-1 underline font-medium">
            Set one in Configuration
          </Link>
          to see usage.
        </Alert>
      ) : usage.data && currentPlan ? (
        <UsageMeters usage={usage.data} limits={currentPlan.limits} />
      ) : null}

      {plans.data && currentPlan && (
        <Box>
          <Heading size="sm" className="mb-3">
            Plans
          </Heading>
          <PlanCards
            plans={plans.data}
            currentTier={currentPlan.tier}
            billingEnabled={billingEnabled}
          />
        </Box>
      )}
    </VStack>
  );
}
