/**
 * Authentication context interface, hook, and role routing helper (FR-01, BR-07).
 */

import { createContext, useContext } from "react";
import type { LoginPayload, Role, User } from "../types/auth";

export interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (payload: LoginPayload) => Promise<User>;
  logout: () => Promise<void>;
  getRoleHome: (role: Role) => string;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function getRoleHome(role: Role): string {
  switch (role) {
    case "RESIDENT":
      return "/requests";
    case "SUPERVISOR":
      return "/triage";
    case "TECHNICIAN":
      return "/work";
    case "WARDEN":
      return "/dashboard";
    case "ADMIN":
      return "/users";
    default:
      return "/login";
  }
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
