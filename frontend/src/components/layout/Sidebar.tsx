import { Box, Divider, Flex, Image, Text, VStack } from "@chakra-ui/react";
import {
  FiActivity,
  FiCreditCard,
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
  { to: "/admin/billing", label: "Billing & Usage", icon: FiCreditCard },
];

function NavItem({ to, label, icon: Icon }: { to: string; label: string; icon: IconType }) {
  return (
    <NavLink to={to} end={to === "/"}>
      {({ isActive }) => (
        <Flex
          className="mx-2 px-4 py-2 rounded-md items-center gap-3 text-sm font-medium transition-colors"
          bg={isActive ? "whiteAlpha.200" : "transparent"}
          color="white"
          _hover={{ bg: isActive ? "whiteAlpha.200" : "whiteAlpha.100" }}
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
      className="w-60 min-h-screen"
      bg="brand.600"
      py={4}
    >
      <Flex className="px-6 mb-6 items-center gap-3">
        <Image src="/logo.png" alt="DocIngest" boxSize="32px" />
        <Text className="text-xl font-bold" color="white">
          DocIngest
        </Text>
      </Flex>
      <VStack spacing={1} align="stretch">
        {navItems.map((item) => (
          <NavItem key={item.to} {...item} />
        ))}
        {isAdmin && (
          <>
            <Divider className="my-2 mx-4" borderColor="whiteAlpha.400" />
            <Text className="px-6 text-xs font-semibold uppercase tracking-wider" color="whiteAlpha.600">
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
