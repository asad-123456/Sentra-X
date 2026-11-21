import React, { useState, useEffect, useRef } from 'react';
import { useOutletContext } from 'react-router-dom';
import {
  Play,
  Download,
  RotateCcw,
  ShieldAlert,
  Sliders,
  FileCode,
  FileText,
  FileSpreadsheet,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import type {
  EvaluationReport,
  SystemConfig,
  User,
  UserRole,
} from '../types/sentrax';
import {
  getBenchmarkReport,
  runBenchmarkEvaluation,
  getDemoSystemConfig,
  updateDemoSystemConfig,
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
import { RuntimeSettingsPanel } from '../components/evaluation/RuntimeSettingsPanel';
import { UserManagementTable } from '../components/evaluation/UserManagementTable';
import type { AppShellContext } from '../components/layout/AppShell';
import { isLiveBackendConfigured } from '../api/client';

type AdminTab = 'benchmark' | 'system_config';
const LIVE_MODE = isLiveBackendConfigured();

const getAdminPanelData = () => Promise.all([LIVE_MODE ? null : getDemoSystemConfig(), getUsers()]);

export const EvaluationRunnerView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<AdminTab>('benchmark');
  const { runtime, refreshRuntime } = useOutletContext<AppShellContext>();
  const showLiveSettings = LIVE_MODE && activeTab === 'system_config';

  // Benchmark State
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [loadingBenchmark, setLoadingBenchmark] = useState(true);
  const [runningBenchmark, setRunningBenchmark] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  // System Config & Users State
  const [systemConfig, setSystemConfig] = useState<SystemConfig | null>(null);
  const [users, setUsers] = useState<User[] | null>(null);
  const [loadingConfig, setLoadingConfig] = useState(true);

  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [showExportMenu, setShowExportMenu] = useState(false);
  const exportMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!runningBenchmark) return;
    const started = Date.now();
    const timer = window.setInterval(() => setElapsedSeconds(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, [runningBenchmark]);

  // Close export menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(event.target as Node)) {
        setShowExportMenu(false);
      }
    };

    if (showExportMenu) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showExportMenu]);

  // Load benchmark initial data
  const loadBenchmarkData = () => {
    setLoadingBenchmark(true);
    setError(null);
    getBenchmarkReport()
      .then((reportData) => {
        setReport(reportData);
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
    getAdminPanelData()
      .then(([configData, usersData]) => {
        setSystemConfig(configData);
        setUsers(usersData);
        setLoadingConfig(false);
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : 'Failed to load user accounts.';
        setError(msg);
        setLoadingConfig(false);
      });
  };

  useEffect(() => {
    let isCancelled = false;
    getBenchmarkReport()
      .then((reportData) => {
        if (!isCancelled) {
          setReport(reportData);
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

    getAdminPanelData()
      .then(([configData, usersData]) => {
        if (!isCancelled) {
          setSystemConfig(configData);
          setUsers(usersData);
          setLoadingConfig(false);
        }
      })
      .catch((err: unknown) => {
        if (!isCancelled) {
          const msg = err instanceof Error ? err.message : 'Failed to load user accounts.';
          setError(msg);
          setLoadingConfig(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, []);

  const handleRunBenchmark = async () => {
    setElapsedSeconds(0);
    setRunningBenchmark(true);
    setActionError(null);
    try {
      const updatedReport = await runBenchmarkEvaluation('SENTRAX_FULL');
      setReport(updatedReport);
    } catch (err) {
      console.error('Failed to run benchmark:', err);
      setActionError(err instanceof Error ? err.message : 'Benchmark evaluation run failed.');
    } finally {
      setRunningBenchmark(false);
    }
  };

  const handleSaveConfig = async (updated: Partial<SystemConfig>) => {
    try {
      const saved = await updateDemoSystemConfig(updated);
      setSystemConfig(saved);
      refreshRuntime();
    } catch (err) {
      console.error('Failed to update config:', err);
      throw err;
    }
  };

  const handleUpdateRole = async (userId: string, role: UserRole) => {
    setActionError(null);
    try {
      const updated = await updateUserRole(userId, role);
      setUsers((prev) => prev?.map((u) => (u.id === updated.id ? updated : u)) ?? null);
    } catch (err) {
      console.error('Failed to update role:', err);
      setActionError(err instanceof Error ? err.message : 'Failed to update user role.');
    }
  };

  const handleToggleActive = async (userId: string, isActive: boolean) => {
    setActionError(null);
    try {
      const updated = await toggleUserActive(userId, isActive);
      setUsers((prev) => prev?.map((u) => (u.id === updated.id ? updated : u)) ?? null);
    } catch (err) {
      console.error('Failed to toggle active status:', err);
      setActionError(err instanceof Error ? err.message : 'Failed to toggle user status.');
    }
  };

  const handleCreateUser = async (newUserData: Omit<User, 'id' | 'created_at'>) => {
    try {
      const { temporary_password: password, ...created } = await createUser(newUserData);
      setUsers((prev) => [...(prev ?? []), created]);
      return password;
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

  const handleExportCSV = () => {
    if (!report) return;
    const rows = [
      ['Run Result', 'Notice'],
      [report.result, `"${report.notice.replace(/"/g, '""')}"`],
      [],
      ['Metric Name', 'Baseline Raw LLM Value', 'Sentra-X Value', 'Research Delta', 'NFR-3 Target Met'],
      ...report.comparative_metrics.map((m) => [
        `"${m.metric_name.replace(/"/g, '""')}"`,
        `"${m.baseline_value.replace(/"/g, '""')}"`,
        `"${m.sentrax_value.replace(/"/g, '""')}"`,
        `"${m.research_delta.replace(/"/g, '""')}"`,
        m.is_target_met ? 'YES' : 'NO',
      ]),
      [],
      ['Payload ID', 'Category', 'Target Field', 'Adversarial Payload', 'Baseline Verdict', 'Baseline Bypassed', 'Sentra-X Verdict', 'Sentra-X Bypassed', 'Defense Mechanism'],
      ...report.adversarial_suite.map((p) => [
        p.id,
        `"${p.category.replace(/"/g, '""')}"`,
        `"${p.target_field.replace(/"/g, '""')}"`,
        `"${p.payload.replace(/"/g, '""')}"`,
        `"${p.baseline_verdict.replace(/"/g, '""')}"`,
        p.baseline_bypassed ? 'YES' : 'NO',
        `"${p.sentrax_verdict.replace(/"/g, '""')}"`,
        p.sentrax_bypassed ? 'YES' : 'NO',
        `"${p.defense_mechanism.replace(/"/g, '""')}"`,
      ]),
    ];

    const csvContent = rows.map((r) => r.join(',')).join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `sentrax_adversarial_evaluation_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    setShowExportMenu(false);
  };

  return (
    <div className="space-y-6">
      {/* Top Header & Execution Actions */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="page-title">
              {showLiveSettings ? 'Runtime and accounts' : 'Adversarial Benchmark'}
            </h1>
            {!showLiveSettings && report?.is_dry_run && (
              <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-zinc-900 text-zinc-400 border border-zinc-800">
                Simulated results
              </span>
            )}
          </div>
          {!showLiveSettings && (
            <p className="text-xs text-zinc-400 mt-0.5">
              Prompt injection test suite and comparative evaluation scorecard.
            </p>
          )}
        </div>

        {/* Action Buttons */}
        <div className={showLiveSettings ? 'hidden' : 'flex flex-wrap items-center gap-2 self-start lg:self-auto'}>
          {/* Run Benchmark CTA */}
          <button
            type="button"
            onClick={handleRunBenchmark}
            disabled={runningBenchmark || loadingBenchmark}
            className="px-4 py-2 rounded-lg bg-zinc-100 text-zinc-950 font-mono text-xs font-semibold hover:bg-zinc-200 transition-colors flex items-center gap-2 shadow-sm disabled:opacity-50"
          >
            {runningBenchmark ? (
              <>
                <Loader2 className="size-3.5 animate-spin text-zinc-950" />
                <span>Running benchmark...</span>
              </>
            ) : (
              <>
                <Play className="size-3.5 fill-current" />
                <span>Run Benchmark Evaluation</span>
              </>
            )}
          </button>

          {/* Export Report Dropdown */}
          <div ref={exportMenuRef} className="relative">
            <button
              type="button"
              onClick={() => setShowExportMenu(!showExportMenu)}
              disabled={!report}
              aria-expanded={showExportMenu}
              className="px-3.5 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-xs font-mono text-zinc-200 hover:text-zinc-50 hover:bg-zinc-800 transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
            >
              <Download className="size-3.5" />
              <span>Export Report</span>
            </button>

            {showExportMenu && (
              <div className="absolute left-0 sm:left-auto sm:right-0 mt-2 w-48 rounded-xl bg-zinc-950 border border-zinc-800 shadow-xl py-1 z-50 animate-in fade-in zoom-in-95" onKeyDown={(event) => {
                if (event.key === 'Escape') {
                  setShowExportMenu(false);
                  exportMenuRef.current?.querySelector('button')?.focus();
                }
              }}>
                <button
                  type="button"
                  onClick={handleExportCSV}
                  className="w-full px-3 py-2 text-left text-xs font-mono text-zinc-300 hover:text-zinc-100 hover:bg-zinc-900 flex items-center gap-2 cursor-pointer"
                >
                  <FileSpreadsheet className="size-3.5 text-zinc-400" />
                  CSV Metrics (.csv)
                </button>
                <button
                  type="button"
                  onClick={handleExportJSON}
                  className="w-full px-3 py-2 text-left text-xs font-mono text-zinc-300 hover:text-zinc-100 hover:bg-zinc-900 flex items-center gap-2 cursor-pointer"
                >
                  <FileCode className="size-3.5 text-zinc-400" />
                  JSON Dataset (.json)
                </button>
                <button
                  type="button"
                  onClick={handleExportMarkdown}
                  className="w-full px-3 py-2 text-left text-xs font-mono text-zinc-300 hover:text-zinc-100 hover:bg-zinc-900 flex items-center gap-2 cursor-pointer"
                >
                  <FileText className="size-3.5 text-zinc-400" />
                  Markdown Report (.md)
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Action Error Banner */}
      {actionError && (
        <div className="p-3 rounded-xl bg-red-950/40 border border-red-800/60 text-xs font-mono text-red-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="size-4 shrink-0 text-red-400" />
            <span>{actionError}</span>
          </div>
          <button
            type="button"
            onClick={() => setActionError(null)}
            className="px-2.5 py-1 rounded bg-zinc-900 border border-zinc-750 text-zinc-300 hover:text-zinc-100 text-[11px]"
          >
            Dismiss
          </button>
        </div>
      )}

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
          {runningBenchmark && (
            <div className="surface flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3 text-sm">
              <p role="status">Benchmark running. A previous report stays available during the run.</p>
              <p className="text-muted-foreground tabular-nums">{elapsedSeconds}s elapsed</p>
            </div>
          )}
          {loadingBenchmark ? (
            <div className="py-20 text-center space-y-3">
              <Loader2 className="size-6 animate-spin text-zinc-500 mx-auto" />
              <div className="text-xs font-mono text-zinc-500">
                Loading adversarial test suite and benchmark scores...
              </div>
            </div>
          ) : report ? (
            <>
              <section aria-labelledby="benchmark-result" className="surface space-y-2 p-4 sm:p-5">
                <h2 id="benchmark-result" className="text-base font-semibold">
                  {report.result === 'inconclusive' ? 'Incomplete run' : report.result === 'passed' ? 'Complete · zero-bypass target met' : 'Complete · zero-bypass target missed'}
                </h2>
                <p className="text-sm text-muted-foreground">
                  {report.total_payloads} injection cases{report.accuracy_set_size != null && ` · ${report.accuracy_set_size} classification cases`}
                  {report.provider && ` · ${report.provider}${report.model ? ` / ${report.model}` : ''}`}
                </p>
                <p className="text-sm text-muted-foreground">{report.notice}</p>
              </section>
              <ScorecardRibbon report={report} />
              <details className="surface min-w-0">
                <summary className="cursor-pointer px-4 py-3 font-medium">Comparative metrics</summary>
                <ComparativeMetricsTable metrics={report.comparative_metrics} inconclusive={report.result === 'inconclusive'} />
              </details>
              <details className="surface min-w-0">
                <summary className="cursor-pointer px-4 py-3 font-medium">Per-case results</summary>
                <AdversarialSuiteTable payloads={report.adversarial_suite} />
              </details>
            </>
          ) : (
            <section className="surface space-y-2 p-4 sm:p-6">
              <h2 className="font-semibold">No benchmark report yet</h2>
              <p className="text-sm text-muted-foreground">The benchmark compares raw and guarded inference on 30 synthetic injection cases and 30 synthetic labelled alerts.</p>
              <p className="text-sm text-muted-foreground">
                {runtime.status === 'ready' && runtime.settings.llm_provider
                  ? `Worker configuration: ${runtime.settings.llm_provider}${runtime.settings.model_name ? ` / ${runtime.settings.model_name}` : ''}.`
                  : 'Worker configuration is currently unavailable.'}
                {' '}If cases fail to complete, the report is marked incomplete and does not receive a pass result.
              </p>
            </section>
          )}
        </div>
      )}

      {/* TAB 2: System Configuration & Role Management */}
      {activeTab === 'system_config' && (
        <div className="space-y-6">
          {LIVE_MODE && <RuntimeSettingsPanel runtime={runtime} onRefresh={refreshRuntime} />}
          {loadingConfig ? (
            <div className="py-20 text-center space-y-3">
              <Loader2 className="size-6 animate-spin text-zinc-500 mx-auto" />
              <div className="text-xs font-mono text-zinc-500">
                Loading user accounts...
              </div>
            </div>
          ) : (
            <>
              {!LIVE_MODE && systemConfig && (
                <SystemConfigPanel config={systemConfig} onSave={handleSaveConfig} />
              )}
              {users && (
                <UserManagementTable
                  users={users}
                  onUpdateRole={handleUpdateRole}
                  onToggleActive={handleToggleActive}
                  onCreateUser={handleCreateUser}
                />
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
};
