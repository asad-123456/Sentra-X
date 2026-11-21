import React, { useRef, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { AlertCircle, ArrowRight } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import type { UserRole } from '../types/sentrax';
import { ApiError } from '../api/client';

export const LoginView: React.FC = () => {
  const { login, isLoading, sessionExpired, switchDemoRole } = useAuth();
  const [usernameOrEmail, setUsernameOrEmail] = useState(switchDemoRole ? 'analyst@sentrax.internal' : '');
  const [password, setPassword] = useState('');
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const passwordField = useRef<HTMLInputElement>(null);

  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/queue';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isLoading) return;
    setErrorBanner(null);

    try {
      await login(usernameOrEmail, password);
      navigate(from, { replace: true });
    } catch (err) {
      const invalid = (err instanceof ApiError && err.status === 401) || !!switchDemoRole;
      setErrorBanner(invalid
        ? 'Check your username or password and try again.'
        : 'Unable to sign in. Try again, or contact your administrator.');
      passwordField.current?.focus();
    }
  };

  const handleQuickRole = (role: UserRole) => {
    if (isLoading || !switchDemoRole) return;
    setErrorBanner(null);
    switchDemoRole(role);
    navigate(from, { replace: true });
  };

  return (
    <main className="min-h-screen bg-background text-foreground flex flex-col justify-center items-center p-5 sm:p-6">

      <div className="w-full max-w-md relative z-10 space-y-6">
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center gap-2.5 px-3.5 py-1.5 rounded-full bg-zinc-900 border border-zinc-800 text-xs font-mono text-zinc-300">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              className="size-3.5 text-zinc-300"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" className="text-zinc-500" />
              <path d="m9 9 6 6" className="text-zinc-100" strokeWidth="2.5" />
              <path d="m15 9-6 6" className="text-zinc-100" strokeWidth="2.5" />
            </svg>
            <span className="font-semibold tracking-wider">SENTRA-X</span>
          </div>
          <h1 className="page-title">
            Security Operations Workspace
          </h1>
        </div>

        {/* Login Card */}
        <div className="surface p-5 sm:p-6 space-y-5">
          {sessionExpired && !errorBanner && <p role="status" className="text-sm text-zinc-200">Sign in again to continue.</p>}
          {/* Inline Error Alert Banner */}
          {errorBanner && (
            <div id="sign-in-error" role="alert" className="p-3 rounded-lg bg-red-950/40 border border-red-800 text-red-200 text-sm flex items-start gap-2">
              <AlertCircle className="size-4 text-red-400 shrink-0 mt-0.5" />
              <span>{errorBanner}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label
                htmlFor="usernameOrEmail"
                className="text-sm font-medium text-foreground"
              >
                Username or Email Address
              </label>
              <input
                id="usernameOrEmail"
                type="text"
                autoComplete="username"
                required
                value={usernameOrEmail}
                onChange={(e) => setUsernameOrEmail(e.target.value)}
                className="field"
              />
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="password"
                className="text-sm font-medium text-foreground"
              >
                Password
              </label>
              <input
                id="password"
                ref={passwordField}
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                aria-describedby={errorBanner ? 'sign-in-error' : undefined}
                className="field"
              />
              {switchDemoRole && <p className="text-[11px] text-zinc-500 font-mono">Demo password: password123</p>}
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-2.5 px-4 rounded-lg bg-zinc-100 text-black font-semibold text-sm hover:bg-white active:bg-zinc-200 transition-colors flex items-center justify-center gap-2 shadow-sm disabled:opacity-50"
            >
              <span>{isLoading ? 'Authenticating...' : 'Sign In to Workspace'}</span>
              <ArrowRight className="size-4" />
            </button>
          </form>

          {switchDemoRole && (
            <div className="pt-4 border-t border-zinc-900 space-y-2">
              <div className="text-[11px] font-mono text-zinc-500 text-center font-semibold">
                DEMO ROLE SELECTOR
              </div>
              <div className="grid grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => handleQuickRole('Analyst')}
                  className="p-2 rounded-md bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-[11px] font-mono text-zinc-300 transition-colors text-center"
                >
                  Analyst
                </button>
                <button
                  type="button"
                  onClick={() => handleQuickRole('TeamLead')}
                  className="p-2 rounded-md bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-[11px] font-mono text-zinc-300 transition-colors text-center"
                >
                  Team Lead
                </button>
                <button
                  type="button"
                  onClick={() => handleQuickRole('Admin')}
                  className="p-2 rounded-md bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-[11px] font-mono text-zinc-300 transition-colors text-center"
                >
                  Admin
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </main>
  );
};

