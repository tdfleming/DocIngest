import {
  Card,
  CardBody,
  Heading,
  Spinner,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr,
  VStack,
} from "@chakra-ui/react";
import { useDocuments } from "../../hooks/useDocuments";
import StatusBadge from "../documents/StatusBadge";

export default function RecentDocuments() {
  const { data, isLoading } = useDocuments({
    per_page: 10,
    sort: "created_at",
    order: "desc",
  });

  if (isLoading) return <Spinner />;

  const docs = data?.documents ?? [];

  return (
    <VStack align="stretch" spacing={3}>
      <Heading size="sm">Recent Documents</Heading>
      <Card size="sm">
        <CardBody className="p-0">
          {docs.length === 0 ? (
            <Text className="p-4 text-gray-500">No documents yet</Text>
          ) : (
            <Table size="sm">
              <Thead>
                <Tr>
                  <Th>Source</Th>
                  <Th>Type</Th>
                  <Th>Status</Th>
                  <Th>Created</Th>
                </Tr>
              </Thead>
              <Tbody>
                {docs.map((doc) => (
                  <Tr key={doc.id}>
                    <Td className="max-w-xs truncate" title={doc.source_ref}>
                      {doc.source_ref}
                    </Td>
                    <Td>{doc.content_type}</Td>
                    <Td>
                      <StatusBadge status={doc.status} />
                    </Td>
                    <Td className="text-xs text-gray-500">
                      {new Date(doc.created_at).toLocaleString()}
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          )}
        </CardBody>
      </Card>
    </VStack>
  );
}
