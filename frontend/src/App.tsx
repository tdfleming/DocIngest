import { ChakraProvider } from "@chakra-ui/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import theme from "./theme";
import { ApiKeyProvider } from "./contexts/ApiKeyContext";
import AppShell from "./components/layout/AppShell";
import DashboardPage from "./pages/DashboardPage";
import DocumentsPage from "./pages/DocumentsPage";
import SearchPage from "./pages/SearchPage";
import ConfigPage from "./pages/ConfigPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      refetchOnWindowFocus: true,
    },
  },
});

export default function App() {
  return (
    <ChakraProvider theme={theme}>
      <QueryClientProvider client={queryClient}>
        <ApiKeyProvider>
          <BrowserRouter>
            <Routes>
              <Route element={<AppShell />}>
                <Route index element={<DashboardPage />} />
                <Route path="documents" element={<DocumentsPage />} />
                <Route path="search" element={<SearchPage />} />
                <Route path="config" element={<ConfigPage />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </ApiKeyProvider>
      </QueryClientProvider>
    </ChakraProvider>
  );
}
