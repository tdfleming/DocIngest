import { useState } from "react";
import {
  Box,
  Button,
  Card,
  CardBody,
  CardHeader,
  FormControl,
  FormLabel,
  Heading,
  Input,
  InputGroup,
  InputRightElement,
  Text,
  useToast,
  VStack,
} from "@chakra-ui/react";
import { useApiKey } from "../../contexts/ApiKeyContext";
import { getHealth } from "../../api/health";

export default function ApiKeyForm() {
  const { apiKey, setApiKey, clearApiKey, isSet } = useApiKey();
  const [draft, setDraft] = useState(apiKey);
  const [show, setShow] = useState(false);
  const [testing, setTesting] = useState(false);
  const toast = useToast();

  const handleSave = () => {
    setApiKey(draft.trim());
    toast({ title: "API key saved", status: "success", duration: 2000 });
  };

  const handleTest = async () => {
    setTesting(true);
    try {
      const health = await getHealth();
      toast({
        title: "Connection successful",
        description: `Status: ${health.status}`,
        status: "success",
        duration: 3000,
      });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Connection failed";
      toast({
        title: "Connection failed",
        description: message,
        status: "error",
        duration: 4000,
      });
    } finally {
      setTesting(false);
    }
  };

  const handleClear = () => {
    clearApiKey();
    setDraft("");
    toast({ title: "API key cleared", status: "info", duration: 2000 });
  };

  return (
    <Card>
      <CardHeader>
        <Heading size="md">API Configuration</Heading>
      </CardHeader>
      <CardBody>
        <VStack spacing={4} align="stretch">
          <FormControl>
            <FormLabel>API Key</FormLabel>
            <InputGroup>
              <Input
                type={show ? "text" : "password"}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="Enter your API key"
              />
              <InputRightElement width="4.5rem">
                <Button
                  h="1.75rem"
                  size="sm"
                  onClick={() => setShow(!show)}
                >
                  {show ? "Hide" : "Show"}
                </Button>
              </InputRightElement>
            </InputGroup>
          </FormControl>

          <Box className="flex gap-3">
            <Button
              colorScheme="blue"
              onClick={handleSave}
              isDisabled={!draft.trim()}
            >
              Save
            </Button>
            <Button onClick={handleTest} isLoading={testing} isDisabled={!isSet}>
              Test Connection
            </Button>
            <Button variant="ghost" onClick={handleClear} isDisabled={!isSet}>
              Clear
            </Button>
          </Box>

          {isSet && (
            <Text className="text-sm text-gray-500">
              API key is set ({apiKey.slice(0, 8)}...)
            </Text>
          )}
        </VStack>
      </CardBody>
    </Card>
  );
}
