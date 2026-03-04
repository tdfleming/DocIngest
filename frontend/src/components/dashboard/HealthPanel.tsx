import {
  Badge,
  Card,
  CardBody,
  Heading,
  SimpleGrid,
  Spinner,
  Text,
  VStack,
} from "@chakra-ui/react";
import { useHealth } from "../../hooks/useHealth";

const SERVICE_LABELS: Record<string, string> = {
  mongodb: "MongoDB",
  qdrant: "Qdrant",
  redis: "Redis",
  minio: "MinIO",
};

export default function HealthPanel() {
  const { data: health, isLoading, isError } = useHealth();

  if (isLoading) return <Spinner />;
  if (isError || !health) {
    return (
      <Card>
        <CardBody>
          <Text color="red.500">Unable to reach API</Text>
        </CardBody>
      </Card>
    );
  }

  return (
    <VStack align="stretch" spacing={3}>
      <Heading size="sm">Service Health</Heading>
      <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4}>
        {Object.entries(health.checks).map(([service, status]) => (
          <Card key={service} size="sm">
            <CardBody className="flex flex-col items-center gap-2">
              <Text className="text-sm font-medium text-gray-600">
                {SERVICE_LABELS[service] ?? service}
              </Text>
              <Badge
                colorScheme={status === "ok" ? "green" : "red"}
                fontSize="sm"
              >
                {status === "ok" ? "Healthy" : "Error"}
              </Badge>
            </CardBody>
          </Card>
        ))}
      </SimpleGrid>
    </VStack>
  );
}
