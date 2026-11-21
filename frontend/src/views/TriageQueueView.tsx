import React, { useEffect, useMemo, useState, useTransition } from 'react';
import { useOutletContext } from 'react-router-dom';
import type { AppShellContext } from '../components/layout/AppShell';
import type { AlertListItem, PaginatedResult, QueueFilters, QueueTab, GuardrailFilter, QueueCounts } from '../types/sentrax';
import { getAlerts, getQueueCounts, quickApprove } from '../api/services';
import { useAuth } from '../context/AuthContext';
import { QueueFilterBar } from '../components/queue/QueueFilterBar';
import { TriageQueueTable } from '../components/queue/TriageQueueTable';
import { AlertDetailModal } from '../components/modal/AlertDetailModal';
import { Button } from '../components/ui/button';
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
  RotateCcw,
} from 'lucide-react';

export const TriageQueueView: React.FC = () => {
  const { user } = useAuth();
  const { setActionableCount } = useOutletContext<AppShellContext>();
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
    filterKey: string;
    data?: PaginatedResult<AlertListItem>;
    error?: string;
  } | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
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
  const [selectedAlert, setSelectedAlert] = useState<{ id: string; opener: HTMLButtonElement } | null>(null);

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
  const filterKey = JSON.stringify(filters);
  const requestKey = JSON.stringify([filterKey, refreshVersion]);
  const activeResult = queueResult?.key === requestKey ? queueResult : null;
  const displayed = queueResult?.filterKey === filterKey ? queueResult.data : undefined;
  const alerts = displayed?.items ?? [];
  const total = displayed?.total ?? 0;
  const totalPages = displayed?.totalPages ?? 1;
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
        setQueueResult({ key: requestKey, filterKey, data });
        setLastUpdated(new Date().toISOString());
      }
    }).catch((error: unknown) => {
      if (!signal.aborted) {
        setQueueResult((previous) => ({
          key: requestKey,
          filterKey,
          data: previous?.filterKey === filterKey ? previous.data : undefined,
          error: error instanceof Error ? error.message : 'Could not load alerts.',
        }));
      }
    });
    return () => controller.abort();
  }, [filters, filterKey, requestKey]);

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
    <div className="flex flex-col gap-4 sm:gap-6">
      {/* Top Header */}
      <div className="flex flex-col sm:-order-2 sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="page-title" id="triage-queue-title" tabIndex={-1}>
            Alert Triage Queue
          </h1>
          <p className="text-sm text-muted-foreground">
            Review and triage incoming security alerts.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <p role="status" className="text-xs text-muted-foreground">
            {isLoading ? (displayed ? 'Refreshing queue…' : 'Loading alerts…') : activeResult?.error ? 'Refresh failed' : `${total} matching`}
            {lastUpdated && <> · Last updated <time dateTime={lastUpdated}>{new Date(lastUpdated).toLocaleTimeString()}</time></>}
          </p>
          <Button variant="outline" onClick={refreshQueue} disabled={isLoading}>
            <RotateCcw className="size-4" aria-hidden="true" /> Refresh queue
          </Button>
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

      {selectedAlert && (
        <AlertDetailModal
          key={selectedAlert.id}
          alertId={selectedAlert.id}
          opener={selectedAlert.opener}
          onClose={() => setSelectedAlert(null)}
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

      {activeResult?.error && (
        <div role="alert" className="flex items-center justify-between gap-3 rounded-lg border border-red-800 bg-red-950/50 p-3 text-sm text-red-200">
          <span>{activeResult.error}</span>
          <button type="button" onClick={refreshQueue} className="shrink-0 rounded border border-red-700 px-3 py-1">
            Retry queue
          </button>
        </div>
      )}
      {(!activeResult?.error || displayed) && (
        <TriageQueueTable
          alerts={alerts}
          isLoading={isLoading}
          onSelectAlert={(id, opener) => setSelectedAlert({ id, opener })}
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
        <div className="flex flex-wrap items-center gap-3">
          {/* Page Size Selector */}
          <div className="flex items-center gap-1.5">
            <span className="text-zinc-500 text-[11px]">SHOW:</span>
            <select
              aria-label="Alerts per page"
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

      {/* Metric KPI Ribbon */}
      <div className="grid grid-cols-2 sm:-order-1 gap-2 sm:gap-4 xl:grid-cols-4">
        {/* Total Pending */}
        <div className="surface min-w-0 p-3 sm:p-4 space-y-1">
          <div className="flex items-center justify-between text-zinc-400 text-xs font-mono">
            <span>Pending review</span>
            <Inbox className="size-4 text-zinc-500" />
          </div>
          <div className="text-2xl font-bold font-mono text-zinc-100">{counts.awaiting}</div>
          <div className="text-xs text-muted-foreground">
            {counts.needsManualTriageCount} require manual triage
          </div>
        </div>

        {/* Critical Safety Floor */}
        <div className="surface min-w-0 p-3 sm:p-4 space-y-1">
          <div className="flex items-center justify-between text-red-400 text-xs font-mono font-medium">
            <span>Critical safety floor</span>
            <ShieldAlert className="size-4 text-red-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-red-300">{counts.criticalSafetyFloor}</div>
          <div className="text-xs text-muted-foreground">High-risk downgrades blocked</div>
        </div>

        {/* Abstention Warnings */}
        <div className="surface min-w-0 p-3 sm:p-4 space-y-1">
          <div className="flex items-center justify-between text-amber-400 text-xs font-mono">
            <span>Model deferred</span>
            <Clock className="size-4 text-amber-500" />
          </div>
          <div className="text-2xl font-bold font-mono text-zinc-100">{counts.abstentionWarnings}</div>
          <div className="text-xs text-muted-foreground">Analyst verdict required</div>
        </div>

        {/* Mean Triage Latency */}
        <div className="surface min-w-0 p-3 sm:p-4 space-y-1">
          <div className="flex items-center justify-between text-zinc-400 text-xs font-mono">
            <span>Mean inference latency</span>
            <Zap className="size-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-emerald-300">
            {counts.meanLatencySeconds == null ? '—' : `${counts.meanLatencySeconds.toFixed(2)}s`}
          </div>
          <div className="text-xs text-muted-foreground">Recorded model call latency</div>
        </div>
      </div>
    </div>
  );
};
