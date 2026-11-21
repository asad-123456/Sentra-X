import React, { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ErrorBoundary } from './components/layout/ErrorBoundary';
import { AppShell } from './components/layout/AppShell';
import { ProtectedRoute } from './components/layout/ProtectedRoute';
import { LoginView } from './views/LoginView';
import { TriageQueueView } from './views/TriageQueueView';

const TeamLeadAnalyticsView = lazy(() => import('./views/TeamLeadAnalyticsView').then((module) => ({ default: module.TeamLeadAnalyticsView })));
const GovernanceView = lazy(() => import('./views/GovernanceView').then((module) => ({ default: module.GovernanceView })));
const EvaluationRunnerView = lazy(() => import('./views/EvaluationRunnerView').then((module) => ({ default: module.EvaluationRunnerView })));
const pageLoading = <p role="status" className="surface p-4 text-sm text-muted-foreground">Loading workspace…</p>;

export default function App(): React.JSX.Element {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public Authentication Route */}
            <Route path="/login" element={<LoginView />} />

            {/* Root Redirect to Triage Queue */}
            <Route path="/" element={<Navigate to="/queue" replace />} />

            {/* Protected Routes inside Global AppShell */}
            <Route
              element={
                <ProtectedRoute>
                  <AppShell />
                </ProtectedRoute>
              }
            >
              {/* Triage Queue: Accessible by Analyst, TeamLead, Admin */}
              <Route
                path="/queue"
                element={
                  <ProtectedRoute allowedRoles={['Analyst', 'TeamLead', 'Admin']}>
                    <TriageQueueView />
                  </ProtectedRoute>
                }
              />

              {/* Agreement Analytics: Accessible by TeamLead, Admin */}
              <Route
                path="/analytics"
                element={
                  <ProtectedRoute allowedRoles={['TeamLead', 'Admin']}>
                    <Suspense fallback={pageLoading}><TeamLeadAnalyticsView /></Suspense>
                  </ProtectedRoute>
                }
              />

              {/* Governance & Assets: Accessible by TeamLead, Admin */}
              <Route
                path="/governance"
                element={
                  <ProtectedRoute allowedRoles={['TeamLead', 'Admin']}>
                    <Suspense fallback={pageLoading}><GovernanceView /></Suspense>
                  </ProtectedRoute>
                }
              />

              {/* Admin Benchmark Runner: Restricted to Admin */}
              <Route
                path="/admin/evaluation"
                element={
                  <ProtectedRoute allowedRoles={['Admin']}>
                    <Suspense fallback={pageLoading}><EvaluationRunnerView /></Suspense>
                  </ProtectedRoute>
                }
              />
            </Route>

            {/* Catch-all Wildcard Redirect */}
            <Route path="*" element={<Navigate to="/queue" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ErrorBoundary>
  );
}
