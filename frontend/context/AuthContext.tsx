"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  ReactNode,
} from "react";
import { api, type UserOut } from "../lib/api";

const STORAGE_KEY = "stellarts_access_token";

interface AuthContextType {
  token: string | null;
  user: UserOut | null;
  login: (token: string, user: UserOut) => void;
  logout: () => void;
  setUser: (user: UserOut | null) => void;
  isAuthenticated: boolean;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUserState] = useState<UserOut | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const setUser = useCallback((u: UserOut | null) => {
    setUserState(u);
  }, []);

  useEffect(() => {
    const stored = typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
    if (stored) {
      setToken(stored);
      api.users
        .me(stored)
        .then((u) => setUserState(u))
        .catch(() => {
          localStorage.removeItem(STORAGE_KEY);
          setToken(null);
          setUserState(null);
        })
        .finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, []);

  const login = useCallback((newToken: string, newUser: UserOut) => {
    setToken(newToken);
    setUserState(newUser);
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY, newToken);
    }
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUserState(null);
    if (typeof window !== "undefined") {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const value: AuthContextType = {
    token,
    user,
    login,
    logout,
    setUser,
    isAuthenticated: !!token,
    isLoading,
  };

  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
