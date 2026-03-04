import { Box, Flex, Text, VStack } from "@chakra-ui/react";
import {
  FiHome,
  FiFile,
  FiSearch,
  FiSettings,
} from "react-icons/fi";
import { NavLink } from "react-router-dom";
import type { IconType } from "react-icons";

const navItems: { to: string; label: string; icon: IconType }[] = [
  { to: "/", label: "Dashboard", icon: FiHome },
  { to: "/documents", label: "Documents", icon: FiFile },
  { to: "/search", label: "Search", icon: FiSearch },
  { to: "/config", label: "Configuration", icon: FiSettings },
];

export default function Sidebar() {
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
          <NavLink key={item.to} to={item.to} end={item.to === "/"}>
            {({ isActive }) => (
              <Flex
                className="mx-2 px-4 py-2 rounded-md items-center gap-3 text-sm font-medium transition-colors"
                bg={isActive ? "brand.50" : "transparent"}
                color={isActive ? "brand.600" : "gray.600"}
                _hover={{ bg: isActive ? "brand.50" : "gray.50" }}
              >
                <item.icon size={18} />
                {item.label}
              </Flex>
            )}
          </NavLink>
        ))}
      </VStack>
    </Box>
  );
}
