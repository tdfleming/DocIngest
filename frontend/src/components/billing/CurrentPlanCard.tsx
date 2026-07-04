import {
  Badge,
  Button,
  Card,
  CardBody,
  Flex,
  Heading,
  Text,
  useToast,
} from "@chakra-ui/react";
import { useState } from "react";
import { openBillingPortal } from "../../api/billing";
import type { SubscriptionResponse } from "../../api/types";
import { formatPrice } from "./format";

const STATUS_COLOR: Record<string, string> = {
  active: "green",
  past_due: "orange",
  canceled: "gray",
};

export default function CurrentPlanCard({
  subscription,
  billingEnabled,
}: {
  subscription: SubscriptionResponse;
  billingEnabled: boolean;
}) {
  const { plan, status } = subscription;
  const toast = useToast();
  const [loading, setLoading] = useState(false);

  const handlePortal = async () => {
    setLoading(true);
    try {
      const { portal_url } = await openBillingPortal();
      window.location.href = portal_url;
    } catch {
      toast({
        title: "Couldn't open the billing portal",
        description: "No active billing profile for this organization yet.",
        status: "info",
        duration: 5000,
      });
      setLoading(false);
    }
  };

  return (
    <Card size="sm">
      <CardBody>
        <Flex className="justify-between items-start gap-4 flex-wrap">
          <div>
            <Text className="text-xs uppercase tracking-wider text-gray-500">
              Current plan
            </Text>
            <Flex className="items-center gap-2 mt-1">
              <Heading size="md">{plan.name}</Heading>
              <Badge colorScheme={STATUS_COLOR[status] ?? "gray"}>{status}</Badge>
            </Flex>
            <Text className="text-sm text-gray-600 mt-1">{formatPrice(plan.price_cents)}</Text>
          </div>
          {billingEnabled && (
            <Button size="sm" variant="outline" onClick={handlePortal} isLoading={loading}>
              Manage billing
            </Button>
          )}
        </Flex>
      </CardBody>
    </Card>
  );
}
