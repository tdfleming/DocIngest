import { useState } from "react";
import {
  Box,
  Button,
  Code,
  Flex,
  FormControl,
  FormLabel,
  IconButton,
  Input,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalOverlay,
  NumberDecrementStepper,
  NumberIncrementStepper,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  Switch,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tooltip,
  Tr,
  useDisclosure,
  useToast,
} from "@chakra-ui/react";
import { FiCopy, FiPlus, FiTrash2 } from "react-icons/fi";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createApiKey, deleteApiKey, updateApiKey } from "../../api/apiKeys";
import type { ApiKeyEntry } from "../../api/types";

interface ApiKeyTableProps {
  keys: ApiKeyEntry[];
}

export default function ApiKeyTable({ keys }: ApiKeyTableProps) {
  const { isOpen, onOpen, onClose } = useDisclosure();
  const {
    isOpen: isKeyShown,
    onOpen: onShowKey,
    onClose: onCloseKey,
  } = useDisclosure();
  const toast = useToast();
  const qc = useQueryClient();

  const [tenantId, setTenantId] = useState("");
  const [tenantName, setTenantName] = useState("");
  const [rateLimit, setRateLimit] = useState(100);
  const [createdKey, setCreatedKey] = useState("");

  const createMutation = useMutation({
    mutationFn: () =>
      createApiKey({
        tenant_id: tenantId,
        tenant_name: tenantName,
        rate_limit: rateLimit,
      }),
    onSuccess: (data) => {
      setCreatedKey(data.api_key);
      qc.invalidateQueries({ queryKey: ["apiKeys"] });
      onClose();
      onShowKey();
      setTenantId("");
      setTenantName("");
      setRateLimit(100);
    },
    onError: () => {
      toast({ title: "Failed to create key", status: "error", duration: 3000 });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (keyId: string) => deleteApiKey(keyId),
    onSuccess: () => {
      toast({ title: "API key deleted", status: "success", duration: 2000 });
      qc.invalidateQueries({ queryKey: ["apiKeys"] });
    },
    onError: () => {
      toast({ title: "Delete failed", status: "error", duration: 3000 });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ keyId, enabled }: { keyId: string; enabled: boolean }) =>
      updateApiKey(keyId, { enabled }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["apiKeys"] });
    },
    onError: () => {
      toast({ title: "Update failed", status: "error", duration: 3000 });
    },
  });

  const copyKey = () => {
    navigator.clipboard.writeText(createdKey);
    toast({ title: "Copied to clipboard", status: "info", duration: 1500 });
  };

  return (
    <Box>
      <Box className="mb-4">
        <Button leftIcon={<FiPlus />} colorScheme="brand" size="sm" onClick={onOpen}>
          Create API Key
        </Button>
      </Box>

      <Table size="sm">
        <Thead>
          <Tr>
            <Th>Key Prefix</Th>
            <Th>Tenant ID</Th>
            <Th>Tenant Name</Th>
            <Th>Rate Limit</Th>
            <Th>Enabled</Th>
            <Th>Created</Th>
            <Th>Actions</Th>
          </Tr>
        </Thead>
        <Tbody>
          {keys.map((k) => (
            <Tr key={k.id}>
              <Td>
                <Code className="text-xs">{k.key_prefix}...</Code>
              </Td>
              <Td className="text-xs">{k.tenant_id}</Td>
              <Td className="text-xs">{k.tenant_name}</Td>
              <Td className="text-xs">{k.rate_limit}</Td>
              <Td>
                <Switch
                  size="sm"
                  isChecked={k.enabled}
                  onChange={() =>
                    toggleMutation.mutate({
                      keyId: k.id,
                      enabled: !k.enabled,
                    })
                  }
                />
              </Td>
              <Td className="text-xs text-gray-500">
                {new Date(k.created_at).toLocaleString()}
              </Td>
              <Td>
                <Tooltip label="Delete key">
                  <IconButton
                    aria-label="Delete"
                    icon={<FiTrash2 />}
                    size="xs"
                    variant="ghost"
                    colorScheme="red"
                    isLoading={deleteMutation.isPending}
                    onClick={() => deleteMutation.mutate(k.id)}
                  />
                </Tooltip>
              </Td>
            </Tr>
          ))}
        </Tbody>
      </Table>

      {/* Create key dialog */}
      <Modal isOpen={isOpen} onClose={onClose}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Create API Key</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <FormControl className="mb-3">
              <FormLabel>Tenant ID</FormLabel>
              <Input
                value={tenantId}
                onChange={(e) => setTenantId(e.target.value)}
                placeholder="e.g. tenant-001"
              />
            </FormControl>
            <FormControl className="mb-3">
              <FormLabel>Tenant Name</FormLabel>
              <Input
                value={tenantName}
                onChange={(e) => setTenantName(e.target.value)}
                placeholder="e.g. Acme Corp"
              />
            </FormControl>
            <FormControl>
              <FormLabel>Rate Limit (req/min)</FormLabel>
              <NumberInput
                value={rateLimit}
                onChange={(_, v) => setRateLimit(v || 100)}
                min={1}
              >
                <NumberInputField />
                <NumberInputStepper>
                  <NumberIncrementStepper />
                  <NumberDecrementStepper />
                </NumberInputStepper>
              </NumberInput>
            </FormControl>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" onClick={onClose} className="mr-2">
              Cancel
            </Button>
            <Button
              colorScheme="brand"
              onClick={() => createMutation.mutate()}
              isLoading={createMutation.isPending}
              isDisabled={!tenantId || !tenantName}
            >
              Create
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Show created key dialog */}
      <Modal isOpen={isKeyShown} onClose={onCloseKey} closeOnOverlayClick={false}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>API Key Created</ModalHeader>
          <ModalBody>
            <Box className="p-3 rounded-md border-2 border-yellow-300" bg="yellow.50">
              <Text className="text-xs text-yellow-700 font-semibold mb-2">
                This key is shown only once. Copy it now!
              </Text>
              <Flex className="items-center gap-2">
                <Code className="flex-1 p-2 text-xs break-all">{createdKey}</Code>
                <IconButton
                  aria-label="Copy"
                  icon={<FiCopy />}
                  size="sm"
                  onClick={copyKey}
                />
              </Flex>
            </Box>
          </ModalBody>
          <ModalFooter>
            <Button onClick={onCloseKey}>Done</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
}
