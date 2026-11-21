import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { ShieldAlert, ArrowLeft } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import type { UserRole } from '../../types/sentrax';

interface ProtectedRouteProps {
  children: React.ReactNode;
  allowedRoles?: UserRole[];
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  allowedRoles,
}) => {
  const { user, token, isLoading, switchDemoRole } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div role="status" className="min-h-screen bg-background flex items-center justify-center text-muted-foreground text-sm">
        Checking your session…
      </div>
    );
  }

  // 1. Unauthenticated -> Redirect to login
  if (!token || !user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // 2. Role Check -> Render HTTP 403 Forbidden card if role insufficient
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return (
      <div className="max-w-2xl mx-auto sm:mt-12">
        <div className="surface border-red-800 p-4 sm:p-6 text-foreground">
          <div className="flex items-start gap-4">
            <div className="p-3 rounded-lg bg-red-950/40 border border-red-500/50 text-red-400">
              <ShieldAlert className="size-6" />
            </div>
            <div className="min-w-0 space-y-2 flex-1">
              <h1 className="text-lg font-semibold">This page requires {allowedRoles.length === 1 ? 'an ' : 'one of these roles: '}{allowedRoles.join(' or ')}{allowedRoles.length === 1 ? ' account' : ''}</h1>
              <p className="text-sm text-muted-foreground">You are signed in as {user.role}.</p>

              <div className="pt-4 border-t border-zinc-800/80 flex flex-wrap items-center justify-between gap-3">
                {switchDemoRole && (
                  <div className="flex items-center gap-2 text-xs text-zinc-400">
                    <span>Switch Demo Role:</span>
                    {allowedRoles.includes('TeamLead') && (
                      <button
                        type="button"
                        onClick={() => switchDemoRole('TeamLead')}
                        className="px-2.5 py-1 rounded bg-zinc-900 border border-zinc-700 hover:border-zinc-500 text-zinc-200 text-xs font-mono transition-colors"
                      >
                        Team Lead
                      </button>
                    )}
                    {allowedRoles.includes('Admin') && (
                      <button
                        type="button"
                        onClick={() => switchDemoRole('Admin')}
                        className="px-2.5 py-1 rounded bg-zinc-900 border border-zinc-700 hover:border-zinc-500 text-zinc-200 text-xs font-mono transition-colors"
                      >
                        Admin
                      </button>
                    )}
                  </div>
                )}

                <a
                  href="/queue"
                  className="inline-flex items-center gap-1.5 text-xs text-zinc-400 hover:text-zinc-200 underline font-mono"
                >
                  <ArrowLeft className="size-3" /> Return to Triage Queue
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
};

