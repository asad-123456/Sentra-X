/**
 * Sentra-X Authentication & RBAC Context
 */

import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import type { User, UserRole } from '../types/sentrax';
import { DEMO_USERS } from '../mock/demoUsers';
import { apiClient, isLiveBackendConfigured } from '../api/client';

interface LoginApiResponse {
  access_token: string;
  user: User;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  sessionExpired: boolean;
  login: (usernameOrEmail: string, password: string) => Promise<void>;
  logout: () => void;
  switchDemoRole?: (role: UserRole) => void;
  hasRole: (allowedRoles: UserRole[]) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const TOKEN_KEY = 'sentrax_jwt_token';
const USER_KEY = 'sentrax_current_user';
const LIVE_MODE = isLiveBackendConfigured();

interface Session {
  user: User;
  token: string;
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [session, setSession] = useState<Session | null>(() => {
    if (LIVE_MODE) return null;
    const token = localStorage.getItem(TOKEN_KEY);
    const user = DEMO_USERS.find((candidate) => token?.startsWith(`jwt-token-${candidate.role.toLowerCase()}-`));
    return token && user ? { token, user } : null;
  });
  const [isRestoring, setIsRestoring] = useState(() => LIVE_MODE && !!localStorage.getItem(TOKEN_KEY));
  const [isSigningIn, setIsSigningIn] = useState(false);
  const [sessionExpired, setSessionExpired] = useState(false);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setSession(null);
    setSessionExpired(false);
  }, []);

  useEffect(() => {
    localStorage.removeItem(USER_KEY);
    if (!LIVE_MODE) return;

    const controller = new AbortController();
    const { signal } = controller;
    const token = localStorage.getItem(TOKEN_KEY);
    const isCurrentToken = () => !signal.aborted && localStorage.getItem(TOKEN_KEY) === token;

    const handleUnauthorized = (event: Event) => {
      if ((event as CustomEvent<string>).detail === localStorage.getItem(TOKEN_KEY)) {
        logout();
        setSessionExpired(true);
      }
    };
    window.addEventListener('sentrax:unauthorized', handleUnauthorized);

    if (token) {
      void apiClient<User>('/api/v1/auth/me', { signal })
        .then((user) => {
          if (isCurrentToken()) setSession({ user, token });
        })
        .catch(() => {
          if (isCurrentToken()) logout();
        })
        .finally(() => {
          if (!signal.aborted) setIsRestoring(false);
        });
    }

    return () => {
      controller.abort();
      window.removeEventListener('sentrax:unauthorized', handleUnauthorized);
    };
  }, [logout]);

  const startSession = (user: User, token: string) => {
    localStorage.setItem(TOKEN_KEY, token);
    setSessionExpired(false);
    setSession({ user, token });
  };

  const startDemoSession = (user: User) => {
    startSession(user, `jwt-token-${user.role.toLowerCase()}-${Date.now()}`);
  };

  const switchDemoRole = LIVE_MODE ? undefined : (role: UserRole) => {
    const user = DEMO_USERS.find((candidate) => candidate.role === role);
    if (user) startDemoSession(user);
  };

  const login = async (usernameOrEmail: string, password: string): Promise<void> => {
    setIsSigningIn(true);
    try {
      if (LIVE_MODE) {
        const { user, access_token } = await apiClient<LoginApiResponse>('/api/v1/auth/login', {
          method: 'POST',
          body: JSON.stringify({ username: usernameOrEmail.trim(), password }),
        });
        startSession(user, access_token);
        return;
      }

      await new Promise((resolve) => setTimeout(resolve, 200));
      const identifier = usernameOrEmail.trim().toLowerCase();
      const user = DEMO_USERS.find(
        (candidate) => candidate.email.toLowerCase() === identifier || candidate.username.toLowerCase() === identifier,
      );
      if (!user || !password.trim()) {
        throw new Error('HTTP 401 Unauthorized: Invalid username, email or password.');
      }
      startDemoSession(user);
    } finally {
      setIsSigningIn(false);
    }
  };

  const user = session?.user ?? null;
  const token = session?.token ?? null;
  const isLoading = isRestoring || isSigningIn;

  const hasRole = (allowedRoles: UserRole[]): boolean => {
    return user !== null && allowedRoles.includes(user.role);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        sessionExpired,
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

