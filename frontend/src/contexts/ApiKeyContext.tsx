import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { API_KEY_STORAGE_KEY } from "../api/client";

interface ApiKeyContextValue {
  apiKey: string;
  setApiKey: (key: string) => void;
  clearApiKey: () => void;
  isSet: boolean;
}

const ApiKeyContext = createContext<ApiKeyContextValue | null>(null);

export function ApiKeyProvider({ children }: { children: ReactNode }) {
  const [apiKey, setApiKeyState] = useState(
    () => localStorage.getItem(API_KEY_STORAGE_KEY) ?? ""
  );

  const setApiKey = useCallback((key: string) => {
    localStorage.setItem(API_KEY_STORAGE_KEY, key);
    setApiKeyState(key);
  }, []);

  const clearApiKey = useCallback(() => {
    localStorage.removeItem(API_KEY_STORAGE_KEY);
    setApiKeyState("");
  }, []);

  const value = useMemo(
    () => ({ apiKey, setApiKey, clearApiKey, isSet: apiKey.length > 0 }),
    [apiKey, setApiKey, clearApiKey]
  );

  return (
    <ApiKeyContext.Provider value={value}>{children}</ApiKeyContext.Provider>
  );
}

export function useApiKey() {
  const ctx = useContext(ApiKeyContext);
  if (!ctx) throw new Error("useApiKey must be used within ApiKeyProvider");
  return ctx;
}
