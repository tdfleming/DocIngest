import { useState } from "react";
import {
  Box,
  Button,
  Card,
  CardBody,
  CardHeader,
  Flex,
  FormControl,
  FormLabel,
  Heading,
  Input,
  Text,
  useToast,
} from "@chakra-ui/react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

export default function LoginPage() {
  const { login, bootstrapAdmin, needsBootstrap, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (isAuthenticated) {
    navigate("/", { replace: true });
    return null;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      if (needsBootstrap) {
        await bootstrapAdmin(username, password);
        toast({
          title: "Admin account created",
          status: "success",
          duration: 2000,
        });
      } else {
        await login(username, password);
      }
      navigate("/", { replace: true });
    } catch (err: unknown) {
      const message =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response
              ?.data?.detail ?? "Authentication failed"
          : "Authentication failed";
      toast({ title: message, status: "error", duration: 3000 });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Flex className="min-h-screen items-center justify-center" bg="gray.50">
      <Card className="w-full max-w-md" shadow="lg">
        <CardHeader className="text-center pb-0">
          <Heading size="lg" color="brand.600">
            DocIngest
          </Heading>
          <Text className="mt-2 text-gray-500">
            {needsBootstrap
              ? "Create Admin Account"
              : "Sign In"}
          </Text>
        </CardHeader>
        <CardBody>
          <form onSubmit={handleSubmit}>
            <FormControl className="mb-4">
              <FormLabel>Username</FormLabel>
              <Input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter username"
                autoFocus
              />
            </FormControl>
            <FormControl className="mb-6">
              <FormLabel>Password</FormLabel>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={
                  needsBootstrap
                    ? "Choose a password (min 8 characters)"
                    : "Enter password"
                }
              />
            </FormControl>
            <Button
              type="submit"
              colorScheme="brand"
              width="full"
              isLoading={isSubmitting}
              isDisabled={!username || !password}
            >
              {needsBootstrap ? "Create Admin Account" : "Sign In"}
            </Button>
            {needsBootstrap && (
              <Box className="mt-4 p-3 rounded-md" bg="blue.50">
                <Text className="text-xs text-blue-700">
                  No users exist yet. Create the first admin account to get
                  started.
                </Text>
              </Box>
            )}
          </form>
        </CardBody>
      </Card>
    </Flex>
  );
}
