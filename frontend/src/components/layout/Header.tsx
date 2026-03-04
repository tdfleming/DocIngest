import { Badge, Flex, Heading, Spinner } from "@chakra-ui/react";
import { useHealth } from "../../hooks/useHealth";
import { useApiKey } from "../../contexts/ApiKeyContext";

interface HeaderProps {
  title: string;
}

export default function Header({ title }: HeaderProps) {
  const { data: health, isLoading } = useHealth();
  const { isSet } = useApiKey();

  return (
    <Flex
      className="px-6 py-4 border-b border-gray-200 items-center justify-between"
      bg="white"
    >
      <Heading size="md">{title}</Heading>
      <Flex className="items-center gap-3">
        {!isSet && (
          <Badge colorScheme="orange" variant="subtle">
            No API Key
          </Badge>
        )}
        {isLoading ? (
          <Spinner size="sm" />
        ) : (
          <Badge
            colorScheme={health?.status === "healthy" ? "green" : "red"}
            variant="subtle"
          >
            {health?.status === "healthy" ? "Connected" : "Degraded"}
          </Badge>
        )}
      </Flex>
    </Flex>
  );
}
