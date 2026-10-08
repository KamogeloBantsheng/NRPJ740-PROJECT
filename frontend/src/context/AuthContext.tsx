/**
 * Authentication Context Provider (FR-01, BR-07).
 */

import React, { useCallback, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { authApi } from "../api/auth";
import type { LoginPayload, User } from "../types/auth";
import { AppError } from "../api/client";
import { AuthContext, getRoleHome } from "./useAuth";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();

  const { data: user = null, isLoading } = useQuery<User | null, AppError>({
    queryKey: ["auth", "me"],
    queryFn: async () => {
      try {
        return await authApi.getMe();
      } catch (err) {
        if (err instanceof AppError && err.statusCode === 401) {
          return null;
        }
        throw err;
      }
    },
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  const loginMutation = useMutation({
    mutationFn: (payload: LoginPayload) => authApi.login(payload),
    onSuccess: (newUser) => {
      queryClient.setQueryData(["auth", "me"], newUser);
    },
  });

  const logoutMutation = useMutation({
    mutationFn: () => authApi.logout(),
    onSuccess: () => {
      queryClient.setQueryData(["auth", "me"], null);
      queryClient.clear();
    },
  });

  const handleLogout = useCallback(async () => {
    await logoutMutation.mutateAsync();
  }, [logoutMutation]);

  const value = useMemo(
    () => ({
      user,
      isLoading,
      isAuthenticated: Boolean(user && user.is_active),
      login: loginMutation.mutateAsync,
      logout: handleLogout,
      getRoleHome,
    }),
    [user, isLoading, loginMutation.mutateAsync, handleLogout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
