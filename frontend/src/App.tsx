import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { AppShell } from './components/layout/AppShell';
import { ProtectedRoute } from './components/layout/ProtectedRoute';
import { LoginView } from './views/LoginView';
import { TriageQueueView } from './views/TriageQueueView';
import { TeamLeadAnalyticsView } from './views/TeamLeadAnalyticsView';
import { GovernanceView } from './views/GovernanceView';
import { EvaluationRunnerView } from './views/EvaluationRunnerView';

export default function App(): React.JSX.Element {
  return (
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
                  <TeamLeadAnalyticsView />
                </ProtectedRoute>
              }
            />

            {/* Governance & Assets: Accessible by TeamLead, Admin */}
            <Route
              path="/governance"
              element={
                <ProtectedRoute allowedRoles={['TeamLead', 'Admin']}>
                  <GovernanceView />
                </ProtectedRoute>
              }
            />

            {/* Admin Benchmark Runner: Restricted to Admin */}
            <Route
              path="/admin/evaluation"
              element={
                <ProtectedRoute allowedRoles={['Admin']}>
                  <EvaluationRunnerView />
                </ProtectedRoute>
              }
            />
          </Route>

          {/* Catch-all Wildcard Redirect */}
          <Route path="*" element={<Navigate to="/queue" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
