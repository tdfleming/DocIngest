import { Badge, Button, Flex, Heading, Spinner, Text } from "@chakra-ui/react";
import { FiLogOut } from "react-icons/fi";
import { useHealth } from "../../hooks/useHealth";
import { useApiKey } from "../../contexts/ApiKeyContext";
import { useAuth } from "../../contexts/AuthContext";

interface HeaderProps {
  title: string;
}

export default function Header({ title }: HeaderProps) {
  const { data: health, isLoading } = useHealth();
  const { isSet } = useApiKey();
  const { user, logout } = useAuth();

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
        {user && (
          <Flex className="items-center gap-2 ml-2 pl-2 border-l border-gray-200">
            <Text className="text-sm text-gray-600">{user.username}</Text>
            <Badge colorScheme={user.role === "admin" ? "purple" : "gray"} variant="subtle" size="sm">
              {user.role}
            </Badge>
            <Button
              size="xs"
              variant="ghost"
              leftIcon={<FiLogOut />}
              onClick={logout}
            >
              Logout
            </Button>
          </Flex>
        )}
      </Flex>
    </Flex>
  );
}
