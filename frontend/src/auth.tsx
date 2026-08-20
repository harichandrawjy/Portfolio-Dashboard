import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { Navigate } from "react-router-dom";

import { api, getToken, setToken, type User } from "./api/client";

interface AuthState {
  user: User | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  demoLogin: () => Promise<void>;
  register: (
    email: string,
    password: string,
    displayName?: string,
  ) => Promise<void>;
  /** Adopt a token minted by a verification or reset link. */
  adoptToken: (token: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      setReady(true);
      return;
    }
    api.me().then(
      (u) => {
        setUser(u);
        setReady(true);
      },
      () => {
        setToken(null); // stale/expired token
        setReady(true);
      },
    );
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await api.login(email, password);
    setToken(access_token);
    setUser(await api.me());
  }, []);

  const demoLogin = useCallback(async () => {
    const { access_token } = await api.demoLogin();
    setToken(access_token);
    setUser(await api.me());
  }, []);

  // Registration no longer signs anyone in: the address has to be confirmed
  // first, and logging in here would just surface the 403 as a failed signup.
  // The caller shows "check your inbox" instead.
  const register = useCallback(
    async (email: string, password: string, displayName?: string) => {
      await api.register(email, password, displayName);
    },
    [],
  );

  const adoptToken = useCallback(async (token: string) => {
    setToken(token);
    setUser(await api.me());
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{ user, ready, login, demoLogin, register, adoptToken, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, ready } = useAuth();
  if (!ready) return null; // avoid login flash while restoring the session
  if (!user) return <Navigate to="/login" replace />;
  return children;
}
