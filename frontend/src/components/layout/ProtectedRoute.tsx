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
      <div className="min-h-screen bg-black flex items-center justify-center text-zinc-400 font-mono text-sm">
        Authenticating session...
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
      <div className="p-8 max-w-2xl mx-auto mt-12">
        <div className="bg-zinc-950 border border-red-500/40 rounded-xl p-6 text-zinc-100 shadow-[0_0_20px_rgba(239,68,68,0.12)]">
          <div className="flex items-start gap-4">
            <div className="p-3 rounded-lg bg-red-950/40 border border-red-500/50 text-red-400">
              <ShieldAlert className="size-6" />
            </div>
            <div className="space-y-2 flex-1">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-red-950/60 text-red-300 border border-red-500/40">
                  HTTP 403 FORBIDDEN
                </span>
                <span className="text-xs text-zinc-500 font-mono">Security Access Policy</span>
              </div>
              <h2 className="text-lg font-semibold text-zinc-50">
                Insufficient Role Permissions
              </h2>
              <p className="text-sm text-zinc-400">
                Your current role <span className="font-mono text-zinc-200 font-bold">[{user.role}]</span> is not authorized to access this route. This view requires one of the following permissions:{' '}
                <span className="font-mono text-zinc-200">
                  [{allowedRoles.join(', ')}]
                </span>.
              </p>

              <div className="pt-4 border-t border-zinc-800/80 flex flex-wrap items-center justify-between gap-3">
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
                      Super Admin
                    </button>
                  )}
                </div>

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

