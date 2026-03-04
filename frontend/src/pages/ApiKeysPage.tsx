import { Card, CardBody, Spinner, Text } from "@chakra-ui/react";
import { useApiKeys } from "../hooks/useApiKeys";
import ApiKeyTable from "../components/apikeys/ApiKeyTable";

export default function ApiKeysPage() {
  const { data: keys, isLoading } = useApiKeys();

  if (isLoading) {
    return <Spinner />;
  }

  return (
    <Card size="sm">
      <CardBody>
        {!keys?.length ? (
          <Text className="text-gray-500 mb-4">
            No API keys found. Create one to get started.
          </Text>
        ) : null}
        <ApiKeyTable keys={keys ?? []} />
      </CardBody>
    </Card>
  );
}
