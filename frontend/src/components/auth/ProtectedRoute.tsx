import { Navigate, Outlet } from "react-router-dom";
import { Flex, Spinner } from "@chakra-ui/react";
import { useAuth } from "../../contexts/AuthContext";

interface ProtectedRouteProps {
  requireAdmin?: boolean;
}

export default function ProtectedRoute({
  requireAdmin = false,
}: ProtectedRouteProps) {
  const { isAuthenticated, isAdmin, isLoading } = useAuth();

  if (isLoading) {
    return (
      <Flex className="min-h-screen items-center justify-center">
        <Spinner size="xl" />
      </Flex>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (requireAdmin && !isAdmin) {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}
