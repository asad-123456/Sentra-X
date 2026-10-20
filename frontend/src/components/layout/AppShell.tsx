import React from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  Inbox,
  BarChart3,
  Sliders,
  Cpu,
  LogOut,
  Radio,
  Sparkles,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import type { UserRole } from '../../types/sentrax';

import { getQueueCounts, getSystemConfig } from '../../api/services';

export const AppShell: React.FC = () => {
  const { user, logout, switchDemoRole } = useAuth();
  const navigate = useNavigate();
  const [actionableCount, setActionableCount] = React.useState<number>(10);
  const [llmLabel, setLlmLabel] = React.useState<string>('Gemini 2.5 Flash');

  React.useEffect(() => {
    getQueueCounts()
      .then((c) => setActionableCount(c.awaiting))
      .catch(() => {});

    getSystemConfig()
      .then((cfg) => {
        setLlmLabel(`${cfg.llm_provider === 'Gemini' ? 'Gemini 2.5 Flash' : 'Claude 3.5 Sonnet'}`);
      })
      .catch(() => {});
  }, []);

  const handleSignOut = () => {
    logout();
    navigate('/login');
  };

  const navItems = [
    {
      to: '/queue',
      label: 'Triage Queue',
      icon: Inbox,
      badge: String(actionableCount),
      allowedRoles: ['Analyst', 'TeamLead', 'Admin'] as UserRole[],
    },
    {
      to: '/analytics',
      label: 'Agreement Analytics',
      icon: BarChart3,
      allowedRoles: ['TeamLead', 'Admin'] as UserRole[],
    },
    {
      to: '/governance',
      label: 'Governance & Assets',
      icon: Sliders,
      allowedRoles: ['TeamLead', 'Admin'] as UserRole[],
    },
    {
      to: '/admin/evaluation',
      label: 'Admin & Benchmark',
      icon: Cpu,
      allowedRoles: ['Admin'] as UserRole[],
    },
  ];

  return (
    <div className="min-h-screen bg-black text-zinc-100 flex flex-col font-sans selection:bg-zinc-800 selection:text-white">
      {/* Persistent Top Status Header */}
      <header className="h-14 border-b border-zinc-800/80 bg-zinc-950/80 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-40">
        <div className="flex items-center gap-6">
          {/* Logo & Identity */}
          <div className="flex items-center gap-2.5">
            <div className="size-7 rounded-md bg-zinc-900 border border-zinc-700/80 flex items-center justify-center text-zinc-100 shadow-[0_0_12px_rgba(255,255,255,0.06)]">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                className="size-4"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" className="text-zinc-400" />
                <path d="m9 9 6 6" className="text-white" strokeWidth="2.5" />
                <path d="m15 9-6 6" className="text-white" strokeWidth="2.5" />
              </svg>
            </div>
            <span className="font-bold tracking-wider text-zinc-50 font-mono text-sm">
              SENTRA-X
            </span>
          </div>

          {/* Active Wazuh Poller Status */}
          <div className="hidden md:flex items-center gap-2 px-2.5 py-1 rounded bg-zinc-900/60 border border-zinc-800 text-xs font-mono text-zinc-300">
            <Radio className="size-3 text-emerald-400 animate-pulse" />
            <span>SIEM: Polling 30s | L &gt;= 4</span>
          </div>

          {/* Active LLM Provider Badge */}
          <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded bg-zinc-900/60 border border-zinc-800 text-xs font-mono text-zinc-300">
            <Sparkles className="size-3 text-cyan-400" />
            <span>LLM: {llmLabel}</span>
          </div>
        </div>

        {/* Right User Bar & Evaluator Role Demo Switcher */}
        <div className="flex items-center gap-3">
          {/* Quick Demo Role Switcher */}
          <div className="hidden sm:flex items-center gap-1 bg-zinc-900/80 p-0.5 rounded-lg border border-zinc-800 text-[11px] font-mono">
            <span className="text-zinc-500 px-2">Demo Role:</span>
            <button
              type="button"
              onClick={() => switchDemoRole('Analyst')}
              className={`px-2 py-0.5 rounded transition-colors ${
                user?.role === 'Analyst'
                  ? 'bg-zinc-100 text-black font-semibold'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Analyst
            </button>
            <button
              type="button"
              onClick={() => switchDemoRole('TeamLead')}
              className={`px-2 py-0.5 rounded transition-colors ${
                user?.role === 'TeamLead'
                  ? 'bg-zinc-100 text-black font-semibold'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              TeamLead
            </button>
            <button
              type="button"
              onClick={() => switchDemoRole('Admin')}
              className={`px-2 py-0.5 rounded transition-colors ${
                user?.role === 'Admin'
                  ? 'bg-zinc-100 text-black font-semibold'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Admin
            </button>
          </div>

          {/* User Role Badge */}
          <div className="flex items-center gap-2 pl-2 border-l border-zinc-800">
            <div className="text-right">
              <div className="text-xs font-medium text-zinc-200">{user?.username || 'Jane Doe'}</div>
              <div className="text-[10px] font-mono text-zinc-500 uppercase">[{user?.role || 'Analyst'}]</div>
            </div>
            <button
              type="button"
              onClick={handleSignOut}
              title="Sign Out"
              className="p-1.5 rounded-md hover:bg-zinc-900 text-zinc-400 hover:text-zinc-100 transition-colors"
            >
              <LogOut className="size-4" />
            </button>
          </div>
        </div>
      </header>

      {/* Main Container: Sidebar + Outlet Viewport */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar Navigation */}
        <aside className="w-64 border-r border-zinc-800/80 bg-zinc-950 flex flex-col justify-between p-4 shrink-0">
          <div className="space-y-6">
            <div>
              <div className="text-[11px] font-mono uppercase tracking-wider text-zinc-500 px-3 mb-2 font-semibold">
                Navigation
              </div>
              <nav className="space-y-1">
                {navItems
                  .filter((item) => !item.allowedRoles || (user && item.allowedRoles.includes(user.role)))
                  .map((item) => {
                  const Icon = item.icon;
                  return (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      className={({ isActive }) =>
                        `flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-colors ${
                          isActive
                            ? 'bg-zinc-100 text-black font-semibold shadow-sm'
                            : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900/70'
                        }`
                      }
                    >
                      <div className="flex items-center gap-2.5">
                        <Icon className="size-4 shrink-0" />
                        <span>{item.label}</span>
                      </div>
                      {item.badge && (
                        <span className="font-mono text-[10px] font-bold px-1.5 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-300">
                          {item.badge}
                        </span>
                      )}
                    </NavLink>
                  );
                })}
              </nav>
            </div>
          </div>
        </aside>

        {/* Dynamic Outlet Viewport */}
        <main className="flex-1 overflow-y-auto bg-black p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
