/**
 * Sentra-X Authentication & RBAC Context
 */

import React, { createContext, useContext, useState } from 'react';
import type { User, UserRole } from '../types/sentrax';
import { DEMO_USERS } from '../mock/demoData';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (usernameOrEmail: string, password: string) => Promise<void>;
  logout: () => void;
  switchDemoRole: (role: UserRole) => void;
  hasRole: (allowedRoles: UserRole[]) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const TOKEN_KEY = 'sentrax_jwt_token';
const USER_KEY = 'sentrax_current_user';

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(() => {
    try {
      const storedUser = localStorage.getItem(USER_KEY);
      const storedToken = localStorage.getItem(TOKEN_KEY);
      if (storedUser && storedToken) {
        return JSON.parse(storedUser);
      }
    } catch {
      // Fallback if parsing fails
    }
    return null;
  });

  const [token, setToken] = useState<string | null>(() => {
    const storedUser = localStorage.getItem(USER_KEY);
    const storedToken = localStorage.getItem(TOKEN_KEY);
    return storedUser && storedToken ? storedToken : null;
  });

  const [isLoading, setIsLoading] = useState<boolean>(false);

  const login = async (usernameOrEmail: string, password: string): Promise<void> => {
    setIsLoading(true);
    await new Promise((resolve) => setTimeout(resolve, 200));

    // Simple credential check against demo accounts or email match
    const foundUser = DEMO_USERS.find(
      (u) =>
        u.email.toLowerCase() === usernameOrEmail.toLowerCase().trim() ||
        u.username.toLowerCase() === usernameOrEmail.toLowerCase().trim()
    );

    if (!foundUser || password.trim().length === 0) {
      setIsLoading(false);
      throw new Error('HTTP 401 Unauthorized: Invalid username, email or password.');
    }

    const mockToken = `jwt-token-${foundUser.role.toLowerCase()}-${Date.now()}`;
    setUser(foundUser);
    setToken(mockToken);
    localStorage.setItem(TOKEN_KEY, mockToken);
    localStorage.setItem(USER_KEY, JSON.stringify(foundUser));
    setIsLoading(false);
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  };

  const switchDemoRole = (role: UserRole) => {
    const targetUser = DEMO_USERS.find((u) => u.role === role) || DEMO_USERS[0];
    const mockToken = `jwt-token-${role.toLowerCase()}-${Date.now()}`;
    setUser(targetUser);
    setToken(mockToken);
    localStorage.setItem(TOKEN_KEY, mockToken);
    localStorage.setItem(USER_KEY, JSON.stringify(targetUser));
  };

  const hasRole = (allowedRoles: UserRole[]): boolean => {
    if (!user) return false;
    return allowedRoles.includes(user.role);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        login,
        logout,
        switchDemoRole,
        hasRole,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

