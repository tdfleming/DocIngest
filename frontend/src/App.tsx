import { ChakraProvider } from "@chakra-ui/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import theme from "./theme";
import { ApiKeyProvider } from "./contexts/ApiKeyContext";
import { AuthProvider } from "./contexts/AuthContext";
import AppShell from "./components/layout/AppShell";
import ProtectedRoute from "./components/auth/ProtectedRoute";
import DashboardPage from "./pages/DashboardPage";
import DocumentsPage from "./pages/DocumentsPage";
import SearchPage from "./pages/SearchPage";
import ConfigPage from "./pages/ConfigPage";
import LoginPage from "./pages/LoginPage";
import UsersPage from "./pages/UsersPage";
import LogsPage from "./pages/LogsPage";
import ApiKeysPage from "./pages/ApiKeysPage";

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
        <AuthProvider>
          <ApiKeyProvider>
            <BrowserRouter>
              <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route element={<ProtectedRoute />}>
                  <Route element={<AppShell />}>
                    <Route index element={<DashboardPage />} />
                    <Route path="documents" element={<DocumentsPage />} />
                    <Route path="search" element={<SearchPage />} />
                    <Route path="config" element={<ConfigPage />} />
                    <Route path="admin/users" element={<UsersPage />} />
                    <Route path="admin/logs" element={<LogsPage />} />
                    <Route path="admin/api-keys" element={<ApiKeysPage />} />
                  </Route>
                </Route>
              </Routes>
            </BrowserRouter>
          </ApiKeyProvider>
        </AuthProvider>
      </QueryClientProvider>
    </ChakraProvider>
  );
}
