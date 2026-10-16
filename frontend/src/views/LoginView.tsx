import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { AlertCircle, ArrowRight } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import type { UserRole } from '../types/sentrax';

export const LoginView: React.FC = () => {
  const [usernameOrEmail, setUsernameOrEmail] = useState('analyst@sentrax.internal');
  const [password, setPassword] = useState('password123');
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { login, switchDemoRole } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/queue';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorBanner(null);
    setIsSubmitting(true);

    try {
      await login(usernameOrEmail, password);
      navigate(from, { replace: true });
    } catch (err) {
      if (err instanceof Error) {
        setErrorBanner(err.message);
      } else {
        setErrorBanner('HTTP 401 Unauthorized: Invalid username or password.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleQuickRole = (role: UserRole) => {
    switchDemoRole(role);
    navigate(from, { replace: true });
  };

  return (
    <div className="min-h-screen bg-black text-zinc-100 flex flex-col justify-center items-center p-6 selection:bg-zinc-800 selection:text-white">
      {/* Background radial accent */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_40%,rgba(255,255,255,0.03),transparent_60%)] pointer-events-none" />

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
          <h1 className="text-2xl font-bold tracking-tight text-zinc-50 font-mono">
            Security Operations Workspace
          </h1>
        </div>

        {/* Login Card */}
        <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-6 shadow-2xl space-y-5">
          {/* Inline Error Alert Banner */}
          {errorBanner && (
            <div className="p-3.5 rounded-lg bg-red-950/30 border border-red-500/40 text-red-300 text-xs font-mono flex items-start gap-2.5 shadow-[0_0_12px_rgba(239,68,68,0.15)]">
              <AlertCircle className="size-4 text-red-400 shrink-0 mt-0.5" />
              <span>{errorBanner}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label
                htmlFor="usernameOrEmail"
                className="text-xs font-mono font-medium text-zinc-300"
              >
                Username or Email Address
              </label>
              <input
                id="usernameOrEmail"
                type="text"
                required
                value={usernameOrEmail}
                onChange={(e) => setUsernameOrEmail(e.target.value)}
                placeholder="analyst@sentrax.internal"
                className="w-full px-3 py-2 rounded-lg bg-black border border-zinc-800 focus:border-zinc-500 text-zinc-100 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-zinc-400 transition-all placeholder:text-zinc-600"
              />
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="password"
                className="text-xs font-mono font-medium text-zinc-300"
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full px-3 py-2 rounded-lg bg-black border border-zinc-800 focus:border-zinc-500 text-zinc-100 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-zinc-400 transition-all placeholder:text-zinc-600"
              />
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full py-2.5 px-4 rounded-lg bg-zinc-100 text-black font-semibold text-sm hover:bg-white active:bg-zinc-200 transition-colors flex items-center justify-center gap-2 shadow-sm disabled:opacity-50"
            >
              <span>{isSubmitting ? 'Authenticating...' : 'Sign In to Workspace'}</span>
              <ArrowRight className="size-4" />
            </button>
          </form>

          {/* Quick Demo Role Switcher */}
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
                Super Admin
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

