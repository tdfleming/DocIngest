import {
  Badge,
  Button,
  Card,
  CardBody,
  Heading,
  List,
  ListItem,
  SimpleGrid,
  Text,
  useToast,
} from "@chakra-ui/react";
import { useState } from "react";
import { createCheckout } from "../../api/billing";
import type { Plan, PlanLimits, PlanTier } from "../../api/types";
import { formatPrice } from "./format";

const LIMIT_LABELS: { key: keyof PlanLimits; noun: string }[] = [
  { key: "ingest", noun: "documents / mo" },
  { key: "search", noun: "searches / mo" },
  { key: "graph_build", noun: "graph builds / mo" },
];

function limitText(value: number | null, noun: string): string {
  return value === null
    ? `Unlimited ${noun}`
    : `${value.toLocaleString()} ${noun}`;
}

export default function PlanCards({
  plans,
  currentTier,
  billingEnabled,
}: {
  plans: Plan[];
  currentTier: PlanTier;
  billingEnabled: boolean;
}) {
  const toast = useToast();
  const [pending, setPending] = useState<PlanTier | null>(null);

  const handleUpgrade = async (tier: PlanTier) => {
    setPending(tier);
    try {
      const { checkout_url } = await createCheckout(tier);
      window.location.href = checkout_url;
    } catch {
      toast({
        title: "Couldn't start checkout",
        description: "Please try again in a moment.",
        status: "error",
        duration: 5000,
      });
      setPending(null);
    }
  };

  return (
    <SimpleGrid columns={{ base: 1, md: 3 }} spacing={4}>
      {plans.map((plan) => {
        const isCurrent = plan.tier === currentTier;
        const isPaid = plan.tier !== "free";
        return (
          <Card key={plan.tier} size="sm" variant={isCurrent ? "filled" : "outline"}>
            <CardBody>
              <div className="flex items-center justify-between mb-1">
                <Heading size="sm">{plan.name}</Heading>
                {isCurrent && <Badge colorScheme="green">Current</Badge>}
              </div>
              <Text className="text-lg font-semibold mb-3">
                {formatPrice(plan.price_cents)}
              </Text>
              <List spacing={1} className="text-sm text-gray-600 mb-4">
                {LIMIT_LABELS.map(({ key, noun }) => (
                  <ListItem key={key}>{limitText(plan.limits[key], noun)}</ListItem>
                ))}
              </List>
              {billingEnabled && isPaid && !isCurrent && (
                <Button
                  size="sm"
                  colorScheme="brand"
                  width="full"
                  isLoading={pending === plan.tier}
                  onClick={() => handleUpgrade(plan.tier)}
                >
                  Upgrade
                </Button>
              )}
            </CardBody>
          </Card>
        );
      })}
    </SimpleGrid>
  );
}
