/**
 * Sentra-X Authentication & RBAC Context
 */

import React, { createContext, useContext, useState } from 'react';
import type { User, UserRole } from '../types/sentrax';
import { DEMO_USERS } from '../mock/demoData';
import { apiClient, isLiveBackendConfigured } from '../api/client';

interface LoginApiResponse {
  access_token: string;
  token_type: string;
  user: {
    id: string;
    username: string;
    email: string;
    role: UserRole;
    is_active: boolean;
    created_at?: string;
  };
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (usernameOrEmail: string, password: string) => Promise<void>;
  logout: () => void;
  switchDemoRole: (role: UserRole) => Promise<void> | void;
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

    // Live backend authentication flow
    if (isLiveBackendConfigured()) {
      try {
        const response = await apiClient<LoginApiResponse>('/api/v1/auth/login', {
          method: 'POST',
          body: JSON.stringify({
            username: usernameOrEmail.trim(),
            password,
          }),
        });

        const liveUser: User = {
          id: String(response.user.id),
          username: response.user.username,
          email: response.user.email,
          role: response.user.role,
          is_active: response.user.is_active,
          created_at: response.user.created_at || new Date().toISOString(),
        };

        setUser(liveUser);
        setToken(response.access_token);
        localStorage.setItem(TOKEN_KEY, response.access_token);
        localStorage.setItem(USER_KEY, JSON.stringify(liveUser));
        setIsLoading(false);
        return;
      } catch (err) {
        setIsLoading(false);
        throw err;
      }
    }

    // Offline / Mock fallback flow
    await new Promise((resolve) => setTimeout(resolve, 200));

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

  const switchDemoRole = async (role: UserRole): Promise<void> => {
    const targetUser = DEMO_USERS.find((u) => u.role === role) || DEMO_USERS[0];
    if (isLiveBackendConfigured()) {
      try {
        await login(targetUser.username, 'sentrax2026');
        return;
      } catch (err) {
        console.warn('Live switchDemoRole failed:', err);
        throw new Error(
          `Live authentication failed for role '${role}'. Verify that the backend is running at ${import.meta.env.VITE_API_BASE_URL} and settings.DEMO_MODE is active.`,
          { cause: err }
        );
      }
    }

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

