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
import { useDocuments } from "../../hooks/useDocuments";

export default function StatsPanel() {
  const { data, isLoading } = useDocuments({ per_page: 200 });

  if (isLoading) return <Spinner />;

  const docs = data?.documents ?? [];
  const total = data?.total ?? 0;
  const pending = docs.filter(
    (d) => d.status === "pending" || d.status === "converting" || d.status === "converted" || d.status === "chunking"
  ).length;
  const complete = docs.filter((d) => d.status === "complete").length;
  const failed = docs.filter((d) => d.status === "failed").length;

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
