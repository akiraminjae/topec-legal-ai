"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext } from "react";
import { api } from "./api";

export interface CurrentUser {
  id: string;
  employee_no: string;
  email: string;
  full_name: string;
  department: string | null;
  roles: string[];
  must_change_password: boolean;
  totp_enabled: boolean;
}

interface AuthContextValue {
  user: CurrentUser | null | undefined;
  isLoading: boolean;
  hasRole: (...roles: string[]) => boolean;
  refetch: () => void;
}

const AuthContext = createContext<AuthContextValue>({
  user: undefined,
  isLoading: true,
  hasRole: () => false,
  refetch: () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { data, isLoading, refetch } = useQuery<CurrentUser | null>({
    queryKey: ["me"],
    queryFn: async () => {
      try {
        const res = await api.get<CurrentUser>("/api/auth/me");
        return res.data;
      } catch {
        return null;
      }
    },
    retry: false,
  });

  const hasRole = (...roles: string[]) => !!data && roles.some((r) => data.roles.includes(r));

  return (
    <AuthContext.Provider value={{ user: data, isLoading, hasRole, refetch: () => refetch() }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

export function useLogout() {
  const queryClient = useQueryClient();
  return async () => {
    await api.post("/api/auth/logout");
    queryClient.setQueryData(["me"], null);
    window.location.href = "/login";
  };
}
