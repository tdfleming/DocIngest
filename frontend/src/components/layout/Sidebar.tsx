import { Box, Divider, Flex, Text, VStack } from "@chakra-ui/react";
import {
  FiActivity,
  FiFile,
  FiHome,
  FiKey,
  FiSearch,
  FiSettings,
  FiUsers,
} from "react-icons/fi";
import { NavLink } from "react-router-dom";
import type { IconType } from "react-icons";
import { useAuth } from "../../contexts/AuthContext";

const navItems: { to: string; label: string; icon: IconType }[] = [
  { to: "/", label: "Dashboard", icon: FiHome },
  { to: "/documents", label: "Documents", icon: FiFile },
  { to: "/search", label: "Search", icon: FiSearch },
  { to: "/config", label: "Configuration", icon: FiSettings },
];

const adminItems: { to: string; label: string; icon: IconType }[] = [
  { to: "/admin/users", label: "Users", icon: FiUsers },
  { to: "/admin/logs", label: "Logs", icon: FiActivity },
  { to: "/admin/api-keys", label: "API Keys", icon: FiKey },
];

function NavItem({ to, label, icon: Icon }: { to: string; label: string; icon: IconType }) {
  return (
    <NavLink to={to} end={to === "/"}>
      {({ isActive }) => (
        <Flex
          className="mx-2 px-4 py-2 rounded-md items-center gap-3 text-sm font-medium transition-colors"
          bg={isActive ? "brand.50" : "transparent"}
          color={isActive ? "brand.600" : "gray.600"}
          _hover={{ bg: isActive ? "brand.50" : "gray.50" }}
        >
          <Icon size={18} />
          {label}
        </Flex>
      )}
    </NavLink>
  );
}

export default function Sidebar() {
  const { isAdmin } = useAuth();

  return (
    <Box
      as="nav"
      className="w-60 min-h-screen border-r border-gray-200"
      bg="white"
      py={4}
    >
      <Text className="px-6 mb-6 text-xl font-bold text-gray-800">
        DocIngest
      </Text>
      <VStack spacing={1} align="stretch">
        {navItems.map((item) => (
          <NavItem key={item.to} {...item} />
        ))}
        {isAdmin && (
          <>
            <Divider className="my-2 mx-4" />
            <Text className="px-6 text-xs font-semibold text-gray-400 uppercase tracking-wider">
              Admin
            </Text>
            {adminItems.map((item) => (
              <NavItem key={item.to} {...item} />
            ))}
          </>
        )}
      </VStack>
    </Box>
  );
}
