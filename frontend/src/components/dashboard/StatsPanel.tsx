import {
  Card,
  CardBody,
  Heading,
  SimpleGrid,
  Spinner,
  Stat,
  StatLabel,
  StatNumber,
  VStack,
} from "@chakra-ui/react";
import { useQuery } from "@tanstack/react-query";
import { getDocumentStats } from "../../api/documents";

export default function StatsPanel() {
  const { data: counts, isLoading } = useQuery({
    queryKey: ["documentStats"],
    queryFn: getDocumentStats,
    refetchInterval: 10_000,
  });

  if (isLoading) return <Spinner />;

  const total = counts?.total ?? 0;
  const pending =
    (counts?.pending ?? 0) +
    (counts?.converting ?? 0) +
    (counts?.converted ?? 0) +
    (counts?.chunking ?? 0);
  const complete = counts?.complete ?? 0;
  const failed = counts?.failed ?? 0;

  const stats = [
    { label: "Total Documents", value: total, color: "blue" },
    { label: "Processing", value: pending, color: "orange" },
    { label: "Complete", value: complete, color: "green" },
    { label: "Failed", value: failed, color: "red" },
  ];

  return (
    <VStack align="stretch" spacing={3}>
      <Heading size="sm">Document Stats</Heading>
      <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4}>
        {stats.map((s) => (
          <Card key={s.label} size="sm">
            <CardBody>
              <Stat>
                <StatLabel>{s.label}</StatLabel>
                <StatNumber color={`${s.color}.500`}>{s.value}</StatNumber>
              </Stat>
            </CardBody>
          </Card>
        ))}
      </SimpleGrid>
    </VStack>
  );
}
