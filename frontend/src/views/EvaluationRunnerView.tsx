import React, { useState, useEffect } from 'react';
import {
  Play,
  Download,
  RotateCcw,
  ShieldAlert,
  Sliders,
  FileCode,
  FileText,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import type {
  EvaluationReport,
  BenchmarkPayload,
  SystemConfig,
  User,
  UserRole,
} from '../types/sentrax';
import {
  getBenchmarkSuite,
  runBenchmarkEvaluation,
  getSystemConfig,
  updateSystemConfig,
  getUsers,
  updateUserRole,
  toggleUserActive,
  createUser,
  generateEvaluationReportMarkdown,
} from '../api/services';
import { ScorecardRibbon } from '../components/evaluation/ScorecardRibbon';
import { ComparativeMetricsTable } from '../components/evaluation/ComparativeMetricsTable';
import { AdversarialSuiteTable } from '../components/evaluation/AdversarialSuiteTable';
import { SystemConfigPanel } from '../components/evaluation/SystemConfigPanel';
import { UserManagementTable } from '../components/evaluation/UserManagementTable';

type AdminTab = 'benchmark' | 'system_config';

export const EvaluationRunnerView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<AdminTab>('benchmark');

  // Benchmark State
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [payloads, setPayloads] = useState<BenchmarkPayload[]>([]);
  const [loadingBenchmark, setLoadingBenchmark] = useState(true);
  const [runningBenchmark, setRunningBenchmark] = useState(false);

  // System Config & Users State
  const [systemConfig, setSystemConfig] = useState<SystemConfig | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [loadingConfig, setLoadingConfig] = useState(true);

  const [error, setError] = useState<string | null>(null);
  const [showExportMenu, setShowExportMenu] = useState(false);

  // Load benchmark initial data
  const loadBenchmarkData = () => {
    setLoadingBenchmark(true);
    setError(null);
    Promise.all([runBenchmarkEvaluation('SENTRAX_FULL'), getBenchmarkSuite()])
      .then(([reportData, suiteData]) => {
        setReport(reportData);
        setPayloads(suiteData);
        setLoadingBenchmark(false);
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : 'Failed to load evaluation data.';
        setError(msg);
        setLoadingBenchmark(false);
      });
  };

  // Load config & users data
  const loadConfigData = () => {
    setLoadingConfig(true);
    Promise.all([getSystemConfig(), getUsers()])
      .then(([configData, usersData]) => {
        setSystemConfig(configData);
        setUsers(usersData);
        setLoadingConfig(false);
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : 'Failed to load system configuration.';
        setError(msg);
        setLoadingConfig(false);
      });
  };

  useEffect(() => {
    let isCancelled = false;
    Promise.all([runBenchmarkEvaluation('SENTRAX_FULL'), getBenchmarkSuite()])
      .then(([reportData, suiteData]) => {
        if (!isCancelled) {
          setReport(reportData);
          setPayloads(suiteData);
          setLoadingBenchmark(false);
        }
      })
      .catch((err: unknown) => {
        if (!isCancelled) {
          const msg = err instanceof Error ? err.message : 'Failed to load evaluation data.';
          setError(msg);
          setLoadingBenchmark(false);
        }
      });

    Promise.all([getSystemConfig(), getUsers()])
      .then(([configData, usersData]) => {
        if (!isCancelled) {
          setSystemConfig(configData);
          setUsers(usersData);
          setLoadingConfig(false);
        }
      })
      .catch((err: unknown) => {
        if (!isCancelled) {
          const msg = err instanceof Error ? err.message : 'Failed to load system configuration.';
          setError(msg);
          setLoadingConfig(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, []);

  const handleRunBenchmark = async () => {
    setRunningBenchmark(true);
    try {
      const updatedReport = await runBenchmarkEvaluation('SENTRAX_FULL');
      setReport(updatedReport);
      setPayloads(updatedReport.adversarial_suite);
    } catch (err) {
      console.error('Failed to run benchmark:', err);
      alert('Benchmark evaluation run failed.');
    } finally {
      setRunningBenchmark(false);
    }
  };

  const handleSaveConfig = async (updated: Partial<SystemConfig>) => {
    try {
      const saved = await updateSystemConfig(updated);
      setSystemConfig(saved);
    } catch (err) {
      console.error('Failed to update config:', err);
      throw err;
    }
  };

  const handleUpdateRole = async (userId: string, role: UserRole) => {
    try {
      const updated = await updateUserRole(userId, role);
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
    } catch (err) {
      console.error('Failed to update role:', err);
      alert('Failed to update user role.');
    }
  };

  const handleToggleActive = async (userId: string, isActive: boolean) => {
    try {
      const updated = await toggleUserActive(userId, isActive);
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
    } catch (err) {
      console.error('Failed to toggle active status:', err);
      alert('Failed to toggle user status.');
    }
  };

  const handleCreateUser = async (newUserData: Omit<User, 'id' | 'created_at'>) => {
    try {
      const created = await createUser(newUserData);
      setUsers((prev) => [...prev, created]);
    } catch (err) {
      console.error('Failed to create user:', err);
      throw err;
    }
  };

  const handleExportJSON = () => {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `sentrax_adversarial_evaluation_${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
    setShowExportMenu(false);
  };

  const handleExportMarkdown = () => {
    if (!report) return;
    const md = generateEvaluationReportMarkdown(report);
    const blob = new Blob([md], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `sentrax_adversarial_evaluation_${new Date().toISOString().slice(0, 10)}.md`;
    a.click();
    URL.revokeObjectURL(url);
    setShowExportMenu(false);
  };

  return (
    <div className="space-y-6">
      {/* Top Header & Execution Actions */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-zinc-50 font-mono">
            Adversarial Benchmark
          </h1>
          <p className="text-xs text-zinc-400 mt-0.5">
            Prompt injection test suite and comparative evaluation scorecard.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2 self-start lg:self-auto">
          {/* Run Benchmark CTA */}
          <button
            type="button"
            onClick={handleRunBenchmark}
            disabled={runningBenchmark}
            className="px-4 py-2 rounded-lg bg-zinc-100 text-zinc-950 font-mono text-xs font-semibold hover:bg-zinc-200 transition-colors flex items-center gap-2 shadow-sm disabled:opacity-50"
          >
            {runningBenchmark ? (
              <>
                <Loader2 className="size-3.5 animate-spin text-zinc-950" />
                <span>Evaluating 30 Payloads...</span>
              </>
            ) : (
              <>
                <Play className="size-3.5 fill-current" />
                <span>Run Benchmark Evaluation</span>
              </>
            )}
          </button>

          {/* Export Report Dropdown */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setShowExportMenu(!showExportMenu)}
              className="px-3.5 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-xs font-mono text-zinc-200 hover:text-zinc-50 hover:bg-zinc-800 transition-colors flex items-center gap-1.5"
            >
              <Download className="size-3.5" />
              <span>Export Report</span>
            </button>

            {showExportMenu && (
              <div className="absolute right-0 mt-2 w-48 rounded-xl bg-zinc-950 border border-zinc-800 shadow-xl py-1 z-50 animate-in fade-in zoom-in-95">
                <button
                  type="button"
                  onClick={handleExportJSON}
                  className="w-full px-3 py-2 text-left text-xs font-mono text-zinc-300 hover:text-zinc-100 hover:bg-zinc-900 flex items-center gap-2"
                >
                  <FileCode className="size-3.5 text-zinc-400" />
                  JSON Dataset (.json)
                </button>
                <button
                  type="button"
                  onClick={handleExportMarkdown}
                  className="w-full px-3 py-2 text-left text-xs font-mono text-zinc-300 hover:text-zinc-100 hover:bg-zinc-900 flex items-center gap-2"
                >
                  <FileText className="size-3.5 text-zinc-400" />
                  Markdown Report (.md)
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Global Error Banner */}
      {error && (
        <div className="p-3 rounded-xl bg-red-950/40 border border-red-800/60 text-xs font-mono text-red-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="size-4 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={() => {
              loadBenchmarkData();
              loadConfigData();
            }}
            className="px-2 py-1 rounded bg-red-900/40 hover:bg-red-900/60 text-red-200 flex items-center gap-1 text-[11px]"
          >
            <RotateCcw className="size-3" />
            Retry
          </button>
        </div>
      )}

      {/* Top Navigation Tabs */}
      <div className="flex border-b border-zinc-800 gap-6">
        <button
          type="button"
          onClick={() => setActiveTab('benchmark')}
          className={`pb-3 text-xs font-mono flex items-center gap-2 border-b-2 transition-all ${
            activeTab === 'benchmark'
              ? 'border-zinc-100 text-zinc-100 font-semibold'
              : 'border-transparent text-zinc-500 hover:text-zinc-300'
          }`}
        >
          <ShieldAlert className="size-4" />
          Adversarial Benchmark
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('system_config')}
          className={`pb-3 text-xs font-mono flex items-center gap-2 border-b-2 transition-all ${
            activeTab === 'system_config'
              ? 'border-zinc-100 text-zinc-100 font-semibold'
              : 'border-transparent text-zinc-500 hover:text-zinc-300'
          }`}
        >
          <Sliders className="size-4" />
          System Configuration
        </button>
      </div>

      {/* TAB 1: Benchmark Runner & Empirical Scorecard */}
      {activeTab === 'benchmark' && (
        <div className="space-y-6">
          {loadingBenchmark ? (
            <div className="py-20 text-center space-y-3">
              <Loader2 className="size-6 animate-spin text-zinc-500 mx-auto" />
              <div className="text-xs font-mono text-zinc-500">
                Loading adversarial test suite and benchmark scores...
              </div>
            </div>
          ) : (
            <>
              {/* Executive Scorecard Ribbon */}
              <ScorecardRibbon report={report} isRunning={runningBenchmark} />

              {/* Comparative Metrics Scorecard Table */}
              {report && (
                <ComparativeMetricsTable metrics={report.comparative_metrics} />
              )}

              {/* 30-Payload Adversarial Test Suite Table */}
              <AdversarialSuiteTable payloads={payloads} />
            </>
          )}
        </div>
      )}

      {/* TAB 2: System Configuration & Role Management */}
      {activeTab === 'system_config' && (
        <div className="space-y-6">
          {loadingConfig || !systemConfig ? (
            <div className="py-20 text-center space-y-3">
              <Loader2 className="size-6 animate-spin text-zinc-500 mx-auto" />
              <div className="text-xs font-mono text-zinc-500">
                Loading system configuration and user accounts...
              </div>
            </div>
          ) : (
            <>
              {/* SIEM & Inference Configuration Panel */}
              <SystemConfigPanel config={systemConfig} onSave={handleSaveConfig} />

              {/* User Accounts & Role Management Table */}
              <UserManagementTable
                users={users}
                onUpdateRole={handleUpdateRole}
                onToggleActive={handleToggleActive}
                onCreateUser={handleCreateUser}
              />
            </>
          )}
        </div>
      )}
    </div>
  );
};
