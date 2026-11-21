import React from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  Inbox,
  BarChart3,
  Sliders,
  Cpu,
  LogOut,
  Radio,
  Sparkles,
  Menu,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import type { RuntimeSettingsState, UserRole } from '../../types/sentrax';
import { isLiveBackendConfigured } from '../../api/client';
import { getDemoSystemConfig, getQueueCounts, getRuntimeSettings } from '../../api/services';
import { Dialog, DialogClose, DialogContent, DialogTitle, DialogTrigger } from '../ui/dialog';
import { Button } from '../ui/button';

const LIVE_MODE = isLiveBackendConfigured();

export interface AppShellContext {
  setActionableCount: (count: number) => void;
  runtime: RuntimeSettingsState;
  refreshRuntime: () => void;
}

export const AppShell: React.FC = () => {
  const { user, logout, switchDemoRole } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [actionableCount, setActionableCount] = React.useState<number | null>(null);
  const [demoLlm, setDemoLlm] = React.useState('Loading…');
  const [runtime, setRuntime] = React.useState<RuntimeSettingsState>({ status: 'loading' });
  const [runtimeRevision, setRuntimeRevision] = React.useState(0);

  React.useEffect(() => {
    getQueueCounts()
      .then((c) => setActionableCount((count) => count ?? c.awaiting))
      .catch(() => {});
  }, []);

  React.useEffect(() => {
    let cancelled = false;
    if (LIVE_MODE) {
      getRuntimeSettings()
        .then((settings) => {
          if (!cancelled) setRuntime({ status: 'ready', settings, checkedAt: new Date().toISOString() });
        })
        .catch(() => {
          if (!cancelled) setRuntime({ status: 'error' });
        });
    } else {
      getDemoSystemConfig()
        .then((config) => {
          if (!cancelled) setDemoLlm(config.model_name);
        })
        .catch(() => {
          if (!cancelled) setDemoLlm('Unavailable');
        });
    }
    return () => { cancelled = true; };
  }, [runtimeRevision]);

  const refreshRuntime = () => {
    setRuntime({ status: 'loading' });
    setRuntimeRevision((revision) => revision + 1);
  };

  const settings = runtime.status === 'ready' ? runtime.settings : null;
  const unavailable = runtime.status === 'loading' ? 'Loading…' : 'Unavailable';

  const handleSignOut = () => {
    logout();
    navigate('/login');
  };

  const navItems = [
    {
      to: '/queue',
      label: 'Triage Queue',
      icon: Inbox,
      badge: actionableCount == null ? undefined : String(actionableCount),
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
  const allowedNav = navItems.filter((item) => user && item.allowedRoles.includes(user.role));
  const locationLabel = allowedNav.find((item) => item.to === pathname)?.label ?? 'Workspace';
  const navigation = (drawer: boolean) => (
    <nav aria-label="Workspace" className="space-y-1">
      {allowedNav.map(({ to, label, icon: Icon, badge }) => {
        const link = (
          <NavLink to={to} className={({ isActive }) =>
            `flex min-h-11 items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${isActive ? 'bg-sidebar-primary text-sidebar-primary-foreground' : 'text-muted-foreground hover:bg-sidebar-accent hover:text-foreground'}`
          }>
            <Icon className="size-4 shrink-0" aria-hidden="true" />
            <span className="flex-1">{label}</span>
            {badge && <span className="rounded bg-zinc-900 px-1.5 text-xs tabular-nums text-zinc-200">{badge}</span>}
          </NavLink>
        );
        return drawer ? <DialogClose key={to} nativeButton={false} render={link} /> : <React.Fragment key={to}>{link}</React.Fragment>;
      })}
    </nav>
  );

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col font-sans">
      <a href="#workspace-main" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[60] focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground">Skip to content</a>
      {/* Persistent Top Status Header */}
      <header className="min-h-14 border-b border-border bg-card px-3 sm:px-5 flex items-center justify-between gap-2 sticky top-0 z-40">
        <div className="flex min-w-0 items-center gap-2 sm:gap-4">
          <Dialog>
            <DialogTrigger className="inline-flex size-11 shrink-0 items-center justify-center rounded-lg text-foreground hover:bg-secondary lg:hidden" aria-label="Open navigation">
              <Menu className="size-5" aria-hidden="true" />
            </DialogTrigger>
            <DialogContent className="left-0 top-0 h-dvh w-72 max-w-[calc(100%-2rem)] translate-x-0 translate-y-0 content-start overflow-y-auto rounded-none sm:max-w-72">
              <DialogTitle>Workspace navigation</DialogTitle>
              <p className="text-sm text-muted-foreground">{user?.role}</p>
              {navigation(true)}
              {switchDemoRole && (
                <label className="grid gap-2 text-sm text-muted-foreground sm:hidden">
                  Demo role
                  <select className="field" value={user?.role} onChange={(event) => switchDemoRole(event.target.value as UserRole)}>
                    <option value="Analyst">Analyst</option>
                    <option value="TeamLead">Team lead</option>
                    <option value="Admin">Admin</option>
                  </select>
                </label>
              )}
            </DialogContent>
          </Dialog>
          {/* Logo & Identity */}
          <div className="hidden sm:flex items-center gap-2.5">
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
          <span className="truncate text-sm font-semibold sm:hidden">{locationLabel}</span>

          <div className="hidden lg:flex items-center gap-2 px-2.5 py-1 rounded bg-secondary border border-border text-xs text-zinc-300">
            <Radio className="size-3 text-zinc-400" aria-hidden="true" />
            <span>{LIVE_MODE ? 'SIEM' : 'Demo SIEM'}: {LIVE_MODE ? settings?.ingestion_mode ?? unavailable : 'Polling 30s | L ≥ 4'}</span>
          </div>

          <div className="hidden xl:flex items-center gap-1.5 px-2.5 py-1 rounded bg-secondary border border-border text-xs text-zinc-300">
            <Sparkles className="size-3 text-zinc-400" aria-hidden="true" />
            <span>
              {LIVE_MODE ? 'LLM' : 'Demo LLM'}: {LIVE_MODE ? settings?.llm_provider ?? settings?.worker_status ?? unavailable : demoLlm}
            </span>
          </div>
        </div>

        {/* Right User Bar & Evaluator Role Demo Switcher */}
        <div className="flex items-center gap-3">
          {switchDemoRole && (
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
          )}

          {/* User Role Badge */}
          <div className="flex items-center gap-2 pl-2 border-l border-zinc-800">
            <div className="text-right">
              <div className="max-w-24 truncate text-xs font-medium text-zinc-200 sm:max-w-44" title={user?.username}>{user?.username}</div>
              <div className="text-xs text-muted-foreground">{user?.role}</div>
            </div>
            <Button variant="ghost" size="icon"
              type="button"
              onClick={handleSignOut}
              title="Sign Out"
              aria-label="Sign out"
              className="size-11"
            >
              <LogOut className="size-4" />
            </Button>
          </div>
        </div>
      </header>

      {/* Main Container: Sidebar + Outlet Viewport */}
      <div className="flex-1 flex min-w-0">
        {/* Left Sidebar Navigation */}
        <aside className="hidden w-56 shrink-0 border-r border-sidebar-border bg-sidebar p-4 lg:block">
          {navigation(false)}
        </aside>

        {/* Dynamic Outlet Viewport */}
        <main id="workspace-main" tabIndex={-1} className="min-w-0 flex-1 p-3 sm:p-6">
          <Outlet context={{ setActionableCount, runtime, refreshRuntime } satisfies AppShellContext} />
        </main>
      </div>
    </div>
  );
};
