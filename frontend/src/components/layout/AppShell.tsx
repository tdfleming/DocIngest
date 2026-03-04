import { Box, Flex } from "@chakra-ui/react";
import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import Header from "./Header";

const titleMap: Record<string, string> = {
  "/": "Dashboard",
  "/documents": "Documents",
  "/search": "Search",
  "/config": "Configuration",
};

export default function AppShell() {
  const { pathname } = useLocation();
  const title = titleMap[pathname] ?? "DocIngest";

  return (
    <Flex className="min-h-screen" bg="gray.50">
      <Sidebar />
      <Box className="flex-1 flex flex-col">
        <Header title={title} />
        <Box className="flex-1 p-6">
          <Outlet />
        </Box>
      </Box>
    </Flex>
  );
}
