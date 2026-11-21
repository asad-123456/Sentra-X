import React, { useEffect, useMemo, useState, useTransition } from 'react';
import { useOutletContext } from 'react-router-dom';
import type { AlertListItem, PaginatedResult, QueueFilters, QueueTab, GuardrailFilter, QueueCounts } from '../types/sentrax';
import { getAlerts, getQueueCounts, quickApprove } from '../api/services';
import { useAuth } from '../context/AuthContext';
import { QueueFilterBar } from '../components/queue/QueueFilterBar';
import { TriageQueueTable } from '../components/queue/TriageQueueTable';
import { AlertDetailModal } from '../components/modal/AlertDetailModal';
import {
  AlertCircle,
  Inbox,
  ShieldAlert,
  Clock,
  Zap,
  CheckCircle2,
  X,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

export const TriageQueueView: React.FC = () => {
  const { user } = useAuth();
  const setActionableCount = useOutletContext<(count: number) => void>();
  const [, startTransition] = useTransition();

  // Filter States
  const [currentTab, setCurrentTab] = useState<QueueTab>('awaiting');
  const [subStatus, setSubStatus] = useState<string>('ALL');
  const [search, setSearch] = useState<string>('');
  const [severity, setSeverity] = useState<string>('ALL');
  const [guardrail, setGuardrail] = useState<GuardrailFilter>('ALL');
  const [assetTier, setAssetTier] = useState<string>('ALL');
  const [ruleId, setRuleId] = useState<string>('');

  // Pagination State
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(5);

  const [refreshVersion, setRefreshVersion] = useState(0);
  const [queueResult, setQueueResult] = useState<{
    key: string;
    data?: PaginatedResult<AlertListItem>;
    error?: string;
  } | null>(null);
  const [counts, setCounts] = useState<QueueCounts>({
    awaiting: 0,
    escalated: 0,
    closed: 0,
    criticalSafetyFloor: 0,
    abstentionWarnings: 0,
    awaitingAnalystCount: 0,
    needsManualTriageCount: 0,
  });

  // Feedback Toast State
  const [notice, setNotice] = useState<{ message: string; failed?: boolean } | null>(null);

  // Selected Alert for inspection modal
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null);

  // Check if any non-default filter is currently active
  const hasActiveFilters =
    search.trim() !== '' ||
    ruleId.trim() !== '' ||
    severity !== 'ALL' ||
    guardrail !== 'ALL' ||
    assetTier !== 'ALL' ||
    subStatus !== 'ALL';

  const filters = useMemo<QueueFilters>(() => ({
    tab: currentTab,
    subStatus,
    severity,
    guardrail,
    assetTier,
    search: search.trim(),
    ruleId: ruleId.trim(),
    page,
    pageSize,
  }), [currentTab, subStatus, severity, guardrail, assetTier, search, ruleId, page, pageSize]);
  const requestKey = JSON.stringify([filters, refreshVersion]);
  const activeResult = queueResult?.key === requestKey ? queueResult : null;
  const alerts = activeResult?.data?.items ?? [];
  const total = activeResult?.data?.total ?? 0;
  const totalPages = activeResult?.data?.totalPages ?? 1;
  const isLoading = activeResult === null;

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    getQueueCounts(signal).then((updatedCounts) => {
      if (!signal.aborted) {
        setCounts(updatedCounts);
        setActionableCount(updatedCounts.awaiting);
      }
    }).catch((error) => {
      if (!signal.aborted) console.error('Failed to load queue counts:', error);
    });
    return () => controller.abort();
  }, [refreshVersion, setActionableCount]);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    getAlerts(filters, signal).then((data) => {
      if (signal.aborted) return;
      if (filters.page > data.totalPages) {
        setPage(data.totalPages);
      } else {
        setQueueResult({ key: requestKey, data });
      }
    }).catch((error: unknown) => {
      if (!signal.aborted) {
        setQueueResult({ key: requestKey, error: error instanceof Error ? error.message : 'Could not load alerts.' });
      }
    });
    return () => controller.abort();
  }, [filters, requestKey]);

  useEffect(() => {
    if (!notice || notice.failed) return;
    const timer = setTimeout(() => setNotice(null), 4500);
    return () => clearTimeout(timer);
  }, [notice]);

  // Reset page to 1 when filters change
  const handleTabChange = (tab: QueueTab) => {
    startTransition(() => {
      setCurrentTab(tab);
      setSubStatus('ALL');
      setPage(1);
    });
  };

  const handleSubStatusChange = (val: string) => {
    startTransition(() => {
      setSubStatus(val);
      setPage(1);
    });
  };

  const handleSearchChange = (val: string) => {
    setSearch(val);
    setPage(1);
  };

  const handleSeverityChange = (val: string) => {
    setSeverity(val);
    setPage(1);
  };

  const handleGuardrailChange = (val: GuardrailFilter) => {
    setGuardrail(val);
    setPage(1);
  };

  const handleAssetTierChange = (val: string) => {
    setAssetTier(val);
    setPage(1);
  };

  const handleResetFilters = () => {
    startTransition(() => {
      setSearch('');
      setRuleId('');
      setSeverity('ALL');
      setGuardrail('ALL');
      setAssetTier('ALL');
      setSubStatus('ALL');
      setPage(1);
    });
  };

  const refreshQueue = () => setRefreshVersion((version) => version + 1);

  const handleDecisionCommitted = (message: string) => {
    setNotice({ message });
    refreshQueue();
  };

  const handleQuickApprove = async (alertId: string) => {
    if (!user) return;
    try {
      const audit = await quickApprove(alertId, user);
      handleDecisionCommitted(`Alert approved. Audit #${audit.id.slice(-6)}.`);
    } catch (error: unknown) {
      setNotice({
        message: error instanceof Error ? error.message : 'The alert could not be approved.',
        failed: true,
      });
      refreshQueue();
    }
  };

  // Calculate item range for pagination label
  const startItem = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const endItem = Math.min(page * pageSize, total);

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-zinc-50 font-mono">
            Alert Triage Queue
          </h1>
          <p className="text-xs text-zinc-400">
            Review and triage incoming security alerts.
          </p>
        </div>

        {/* Live Status Pill */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-zinc-950 border border-zinc-800 text-xs font-mono text-zinc-400 self-start sm:self-auto">
          <span className="size-2 rounded-full bg-emerald-500 animate-pulse" />
          <span>Stream Active</span>
          <span className="text-zinc-700">•</span>
          <span className="text-zinc-300 font-semibold">{total} matching</span>
        </div>
      </div>

      {/* Metric KPI Ribbon */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Pending */}
        <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-800 space-y-1 shadow-sm">
          <div className="flex items-center justify-between text-zinc-400 text-xs font-mono">
            <span>TOTAL PENDING</span>
            <Inbox className="size-4 text-zinc-500" />
          </div>
          <div className="text-2xl font-bold font-mono text-zinc-100">{counts.awaiting}</div>
          <div className="text-[11px] text-zinc-500 font-mono">
            {counts.needsManualTriageCount} require manual triage
          </div>
        </div>

        {/* Critical Safety Floor */}
        <div className="p-4 rounded-xl bg-zinc-950 border border-red-500/30 space-y-1 shadow-[0_0_14px_rgba(239,68,68,0.06)]">
          <div className="flex items-center justify-between text-red-400 text-xs font-mono font-medium">
            <span>CRITICAL SAFETY FLOOR</span>
            <ShieldAlert className="size-4 text-red-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-red-300">{counts.criticalSafetyFloor}</div>
          <div className="text-[11px] text-red-400/80 font-mono">Level &gt;= 12 mandatory human review</div>
        </div>

        {/* Abstention Warnings */}
        <div className="p-4 rounded-xl bg-zinc-950 border border-amber-500/30 space-y-1 shadow-[0_0_14px_rgba(245,158,11,0.05)]">
          <div className="flex items-center justify-between text-amber-400 text-xs font-mono">
            <span>ABSTENTION WARNINGS</span>
            <Clock className="size-4 text-amber-500" />
          </div>
          <div className="text-2xl font-bold font-mono text-zinc-100">{counts.abstentionWarnings}</div>
          <div className="text-[11px] text-zinc-500 font-mono">Confidence &lt; 60% threshold</div>
        </div>

        {/* Mean Triage Latency */}
        <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-800 space-y-1 shadow-sm">
          <div className="flex items-center justify-between text-zinc-400 text-xs font-mono">
            <span>MEAN INFERENCE LATENCY</span>
            <Zap className="size-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-emerald-300">
            {counts.meanLatencySeconds == null ? '—' : `${counts.meanLatencySeconds.toFixed(2)}s`}
          </div>
          <div className="text-[11px] text-zinc-500 font-mono">Recorded model call latency</div>
        </div>
      </div>

      {notice && (
        <div
          role={notice.failed ? 'alert' : 'status'}
          className={`flex items-center justify-between gap-3 rounded-lg border p-3 text-xs font-mono ${
            notice.failed ? 'bg-red-950/60 border-red-800 text-red-200' : 'bg-emerald-950/60 border-emerald-800 text-emerald-200'
          }`}
        >
          <div className="flex items-center gap-2">
            {notice.failed ? <AlertCircle className="size-4 shrink-0" /> : <CheckCircle2 className="size-4 shrink-0" />}
            <span>{notice.message}</span>
          </div>
          <button type="button" onClick={() => setNotice(null)} className="p-1" aria-label="Dismiss notice">
            <X className="size-3.5" />
          </button>
        </div>
      )}

      {selectedAlertId && (
        <AlertDetailModal
          key={selectedAlertId}
          alertId={selectedAlertId}
          onClose={() => setSelectedAlertId(null)}
          onDecisionCommitted={handleDecisionCommitted}
        />
      )}

      {/* Filter and Queue Navigation Controls */}
      <QueueFilterBar
        currentTab={currentTab}
        onTabChange={handleTabChange}
        subStatus={subStatus}
        onSubStatusChange={handleSubStatusChange}
        search={search}
        onSearchChange={handleSearchChange}
        ruleId={ruleId}
        onRuleIdChange={(val) => {
          setRuleId(val);
          setPage(1);
        }}
        severity={severity}
        onSeverityChange={handleSeverityChange}
        guardrail={guardrail}
        onGuardrailChange={handleGuardrailChange}
        assetTier={assetTier}
        onAssetTierChange={handleAssetTierChange}
        counts={counts}
        onResetFilters={handleResetFilters}
        hasActiveFilters={hasActiveFilters}
      />

      {activeResult?.error ? (
        <div role="alert" className="flex items-center justify-between gap-3 rounded-lg border border-red-800 bg-red-950/50 p-3 text-sm text-red-200">
          <span>{activeResult.error}</span>
          <button type="button" onClick={refreshQueue} className="shrink-0 rounded border border-red-700 px-3 py-1">
            Retry queue
          </button>
        </div>
      ) : (
        <TriageQueueTable
          alerts={alerts}
          isLoading={isLoading}
          onSelectAlert={setSelectedAlertId}
          onQuickApprove={handleQuickApprove}
          hasActiveFilters={hasActiveFilters}
          onResetFilters={handleResetFilters}
        />
      )}

      {/* Pagination Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs font-mono text-zinc-400 border-t border-zinc-900 pt-3">
        {/* Left: Showing range */}
        <div>
          Showing <span className="text-zinc-200 font-semibold">{startItem}</span>–
          <span className="text-zinc-200 font-semibold">{endItem}</span> of{' '}
          <span className="text-zinc-200 font-semibold">{total}</span> alerts
        </div>

        {/* Right: Controls & Page size */}
        <div className="flex items-center gap-4">
          {/* Page Size Selector */}
          <div className="flex items-center gap-1.5">
            <span className="text-zinc-500 text-[11px]">SHOW:</span>
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(1);
              }}
              className="bg-zinc-900 border border-zinc-800 text-zinc-300 text-xs rounded px-2 py-1 font-mono focus:outline-none focus:border-zinc-700 cursor-pointer"
            >
              <option value={5}>5 per page</option>
              <option value={10}>10 per page</option>
              <option value={25}>25 per page</option>
            </select>
          </div>

          {/* Page Navigation */}
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setPage((prev) => Math.max(prev - 1, 1))}
              disabled={page <= 1 || isLoading}
              className="p-1 rounded bg-zinc-900 border border-zinc-800 text-zinc-300 hover:text-zinc-100 hover:bg-zinc-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              title="Previous page"
            >
              <ChevronLeft className="size-4" />
            </button>

            <span className="px-2 text-zinc-300">
              Page <span className="text-zinc-100 font-semibold">{page}</span> of{' '}
              <span className="text-zinc-100 font-semibold">{totalPages}</span>
            </span>

            <button
              type="button"
              onClick={() => setPage((prev) => Math.min(prev + 1, totalPages))}
              disabled={page >= totalPages || isLoading}
              className="p-1 rounded bg-zinc-900 border border-zinc-800 text-zinc-300 hover:text-zinc-100 hover:bg-zinc-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              title="Next page"
            >
              <ChevronRight className="size-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
