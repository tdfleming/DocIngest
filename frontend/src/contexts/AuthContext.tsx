import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { JWT_STORAGE_KEY } from "../api/client";
import { getAuthStatus, getMe, login as apiLogin, bootstrap as apiBootstrap } from "../api/auth";
import type { UserResponse } from "../api/types";

interface AuthContextValue {
  user: UserResponse | null;
  isAuthenticated: boolean;
  isAdmin: boolean;
  isLoading: boolean;
  needsBootstrap: boolean;
  login: (username: string, password: string) => Promise<void>;
  bootstrapAdmin: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [needsBootstrap, setNeedsBootstrap] = useState(false);

  useEffect(() => {
    const init = async () => {
      try {
        const jwt = localStorage.getItem(JWT_STORAGE_KEY);
        if (jwt) {
          const me = await getMe();
          setUser(me);
        } else {
          const status = await getAuthStatus();
          setNeedsBootstrap(!status.has_users);
        }
      } catch {
        localStorage.removeItem(JWT_STORAGE_KEY);
        try {
          const status = await getAuthStatus();
          setNeedsBootstrap(!status.has_users);
        } catch {
          // API might be down
        }
      } finally {
        setIsLoading(false);
      }
    };
    init();
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await apiLogin(username, password);
    localStorage.setItem(JWT_STORAGE_KEY, res.access_token);
    setUser(res.user);
    setNeedsBootstrap(false);
  }, []);

  const bootstrapAdmin = useCallback(
    async (username: string, password: string) => {
      const res = await apiBootstrap(username, password);
      localStorage.setItem(JWT_STORAGE_KEY, res.access_token);
      setUser(res.user);
      setNeedsBootstrap(false);
    },
    []
  );

  const logout = useCallback(() => {
    localStorage.removeItem(JWT_STORAGE_KEY);
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({
      user,
      isAuthenticated: user !== null,
      isAdmin: user?.role === "admin",
      isLoading,
      needsBootstrap,
      login,
      bootstrapAdmin,
      logout,
    }),
    [user, isLoading, needsBootstrap, login, bootstrapAdmin, logout]
  );

  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
