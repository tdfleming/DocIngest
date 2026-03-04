import { Card, CardBody, Spinner, Text } from "@chakra-ui/react";
import { useUsers } from "../hooks/useUsers";
import { useAuth } from "../contexts/AuthContext";
import UserTable from "../components/users/UserTable";

export default function UsersPage() {
  const { data: users, isLoading } = useUsers();
  const { user } = useAuth();

  if (isLoading) {
    return <Spinner />;
  }

  if (!users?.length) {
    return <Text className="text-gray-500">No users found</Text>;
  }

  return (
    <Card size="sm">
      <CardBody>
        <UserTable users={users} currentUserId={user?.id ?? ""} />
      </CardBody>
    </Card>
  );
}
