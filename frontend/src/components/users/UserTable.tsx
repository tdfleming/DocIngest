import { useState } from "react";
import {
  Badge,
  Box,
  Button,
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
  Select,
  Table,
  Tbody,
  Td,
  Th,
  Thead,
  Tooltip,
  Tr,
  useDisclosure,
  useToast,
} from "@chakra-ui/react";
import { FiPlus, FiTrash2 } from "react-icons/fi";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createUser, deleteUser } from "../../api/auth";
import type { UserResponse, UserRole } from "../../api/types";

interface UserTableProps {
  users: UserResponse[];
  currentUserId: string;
}

export default function UserTable({ users, currentUserId }: UserTableProps) {
  const { isOpen, onOpen, onClose } = useDisclosure();
  const toast = useToast();
  const qc = useQueryClient();

  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState<UserRole>("viewer");

  const createMutation = useMutation({
    mutationFn: () =>
      createUser({
        username: newUsername,
        password: newPassword,
        role: newRole,
      }),
    onSuccess: () => {
      toast({ title: "User created", status: "success", duration: 2000 });
      qc.invalidateQueries({ queryKey: ["users"] });
      onClose();
      setNewUsername("");
      setNewPassword("");
      setNewRole("viewer");
    },
    onError: (err: unknown) => {
      const message =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response
              ?.data?.detail ?? "Failed to create user"
          : "Failed to create user";
      toast({ title: message, status: "error", duration: 3000 });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (userId: string) => deleteUser(userId),
    onSuccess: () => {
      toast({ title: "User deleted", status: "success", duration: 2000 });
      qc.invalidateQueries({ queryKey: ["users"] });
    },
    onError: () => {
      toast({ title: "Delete failed", status: "error", duration: 3000 });
    },
  });

  return (
    <Box>
      <Box className="mb-4">
        <Button leftIcon={<FiPlus />} colorScheme="brand" size="sm" onClick={onOpen}>
          Create User
        </Button>
      </Box>

      <Table size="sm">
        <Thead>
          <Tr>
            <Th>Username</Th>
            <Th>Role</Th>
            <Th>Created</Th>
            <Th>Actions</Th>
          </Tr>
        </Thead>
        <Tbody>
          {users.map((u) => (
            <Tr key={u.id}>
              <Td>{u.username}</Td>
              <Td>
                <Badge
                  colorScheme={u.role === "admin" ? "purple" : "gray"}
                  variant="subtle"
                >
                  {u.role}
                </Badge>
              </Td>
              <Td className="text-xs text-gray-500">
                {new Date(u.created_at).toLocaleString()}
              </Td>
              <Td>
                <Tooltip
                  label={
                    u.id === currentUserId
                      ? "Cannot delete yourself"
                      : "Delete user"
                  }
                >
                  <IconButton
                    aria-label="Delete"
                    icon={<FiTrash2 />}
                    size="xs"
                    variant="ghost"
                    colorScheme="red"
                    isDisabled={u.id === currentUserId}
                    isLoading={deleteMutation.isPending}
                    onClick={() => deleteMutation.mutate(u.id)}
                  />
                </Tooltip>
              </Td>
            </Tr>
          ))}
        </Tbody>
      </Table>

      <Modal isOpen={isOpen} onClose={onClose}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Create User</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <FormControl className="mb-3">
              <FormLabel>Username</FormLabel>
              <Input
                value={newUsername}
                onChange={(e) => setNewUsername(e.target.value)}
                placeholder="Username (min 3 characters)"
              />
            </FormControl>
            <FormControl className="mb-3">
              <FormLabel>Password</FormLabel>
              <Input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Password (min 8 characters)"
              />
            </FormControl>
            <FormControl>
              <FormLabel>Role</FormLabel>
              <Select
                value={newRole}
                onChange={(e) => setNewRole(e.target.value as UserRole)}
              >
                <option value="viewer">Viewer</option>
                <option value="admin">Admin</option>
              </Select>
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
              isDisabled={
                newUsername.length < 3 || newPassword.length < 8
              }
            >
              Create
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
}
