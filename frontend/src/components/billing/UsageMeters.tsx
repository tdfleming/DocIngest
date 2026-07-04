import {
  Box,
  Card,
  CardBody,
  Flex,
  Heading,
  Progress,
  Text,
  VStack,
} from "@chakra-ui/react";
import type { PlanLimits, UsageSummary } from "../../api/types";

const METRICS: { key: keyof PlanLimits; label: string }[] = [
  { key: "ingest", label: "Documents ingested" },
  { key: "search", label: "Searches" },
  { key: "graph_build", label: "Graph builds" },
];

function meterColor(ratio: number): string {
  if (ratio >= 1) return "red";
  if (ratio >= 0.8) return "orange";
  return "green";
}

export default function UsageMeters({
  usage,
  limits,
}: {
  usage: UsageSummary;
  limits: PlanLimits;
}) {
  return (
    <Card size="sm">
      <CardBody>
        <Heading size="sm" className="mb-1">
          This month's usage
        </Heading>
        <Text className="text-xs text-gray-500 mb-4">
          Since {new Date(usage.period_start).toLocaleDateString()}
        </Text>
        <VStack align="stretch" spacing={4}>
          {METRICS.map(({ key, label }) => {
            const used = usage.events[key] ?? 0;
            const limit = limits[key];
            const unlimited = limit === null;
            const ratio = unlimited || limit === 0 ? 0 : used / limit;
            return (
              <Box key={key}>
                <Flex className="justify-between items-baseline mb-1">
                  <Text className="text-sm font-medium">{label}</Text>
                  <Text className="text-sm text-gray-600">
                    {used.toLocaleString()}
                    {unlimited ? " (unlimited)" : ` / ${limit.toLocaleString()}`}
                  </Text>
                </Flex>
                <Progress
                  value={unlimited ? 100 : Math.min(100, ratio * 100)}
                  size="sm"
                  borderRadius="full"
                  colorScheme={unlimited ? "blue" : meterColor(ratio)}
                  opacity={unlimited ? 0.35 : 1}
                />
              </Box>
            );
          })}
        </VStack>
      </CardBody>
    </Card>
  );
}
