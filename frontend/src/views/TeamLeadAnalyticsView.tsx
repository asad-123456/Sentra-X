import React, { useState, useEffect } from 'react';
import type { AnalyticsSummary } from '../types/sentrax';
import { getAnalytics, exportAuditCsv } from '../api/services';
import { isLiveBackendConfigured } from '../api/client';
import { KpiSummaryGrid } from '../components/analytics/KpiSummaryGrid';
import { OverrideTrendChart } from '../components/analytics/OverrideTrendChart';
import { SeverityDeltaCard } from '../components/analytics/SeverityDeltaCard';
import {
  Download,
  RotateCcw,
  Check,
  AlertCircle,
  Calendar,
  Filter,
} from 'lucide-react';

export const TeamLeadAnalyticsView: React.FC = () => {
  const live = isLiveBackendConfigured();
  const [dateRange, setDateRange] = useState<string>('30d');
  const [selectedRuleId, setSelectedRuleId] = useState<string>('ALL');
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [report, setReport] = useState<{ key: string; data?: AnalyticsSummary; error?: string } | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [exportSuccess, setExportSuccess] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const requestKey = JSON.stringify([dateRange, selectedRuleId, refreshVersion]);
  const current = report?.key === requestKey ? report : null;
  const analytics = current?.data;
  const error = current?.error;
  const isLoading = !current;

  const handleRefresh = () => {
    setExportError(null);
    setRefreshVersion((version) => version + 1);
  };

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    getAnalytics(dateRange, selectedRuleId, signal)
      .then((data) => {
        if (!signal.aborted) setReport({ key: requestKey, data });
      })
      .catch((err: unknown) => {
        if (!signal.aborted) {
          const message = err instanceof Error ? err.message : 'Analytics data could not be retrieved.';
          setReport({ key: requestKey, error: message });
        }
      });
    return () => controller.abort();
  }, [dateRange, selectedRuleId, requestKey]);

  useEffect(() => {
    if (!exportSuccess) return;
    const timer = setTimeout(() => setExportSuccess(false), 3000);
    return () => clearTimeout(timer);
  }, [exportSuccess]);

  const handleExport = async () => {
    setIsExporting(true);
    setExportError(null);
    try {
      const csvData = await exportAuditCsv(analytics?.report_window);
      const blob = new Blob([csvData], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const today = analytics?.report_window?.end_date ?? new Date().toISOString().slice(0, 10);
      link.setAttribute('download', `sentrax_audit_trail_${today}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);

      setExportSuccess(true);
    } catch (err) {
      console.error('CSV Export failed:', err);
      setExportError(err instanceof Error ? err.message : 'Failed to generate audit CSV export.');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* View Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-zinc-50 font-mono">
              Triage Analytics &amp; Calibration
            </h1>
            {!live && <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-zinc-900 text-zinc-400 border border-zinc-800">
              Simulated Demo Fixture
            </span>}
          </div>
          <p className="text-xs text-zinc-400 font-sans">
            Analyst agreement, overrides, and audit records. Dates are in UTC.
          </p>
        </div>

        {/* Header Actions: CSV Export Button */}
        <div className="flex items-center gap-2.5 self-start md:self-auto">
          <button
            type="button"
            onClick={handleRefresh}
            disabled={isLoading}
            className="p-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer"
            title="Refresh telemetry"
          >
            <RotateCcw className={`size-4 ${isLoading ? 'animate-spin text-cyan-400' : ''}`} />
          </button>

          <button
            type="button"
            onClick={handleExport}
            disabled={isExporting || (live && !analytics?.report_window)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-white hover:bg-zinc-200 text-black font-semibold text-xs font-mono shadow-md transition-all cursor-pointer disabled:opacity-60"
          >
            {exportSuccess ? (
              <>
                <Check className="size-3.5 text-emerald-600" />
                <span>Export Downloaded</span>
              </>
            ) : (
              <>
                <Download className="size-3.5 text-black" />
                <span>{isExporting ? 'Generating CSV...' : 'Export Audit CSV'}</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Filter Toolbar: Date Presets & Rule Filter */}
      <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-850 flex flex-wrap items-center justify-between gap-3">
        {/* Date Presets */}
        <div className="flex items-center gap-1.5">
          <div className="flex items-center gap-1.5 text-zinc-500 font-mono text-xs pr-2">
            <Calendar className="size-3.5 text-zinc-400" />
            <span className="hidden sm:inline">Range:</span>
          </div>
          <div className="flex items-center gap-1 p-0.5 bg-zinc-900 rounded-lg border border-zinc-800">
            {[
              { id: '7d', label: 'Last 7 Days' },
              { id: '30d', label: 'Last 30 Days' },
              { id: '90d', label: 'Last 90 Days' },
            ].map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setDateRange(p.id)}
                className={`px-3 py-1 rounded-md text-xs font-mono font-medium transition-colors cursor-pointer ${
                  dateRange === p.id
                    ? 'bg-zinc-800 text-zinc-100 border border-zinc-700 shadow-sm'
                    : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        {/* Rule filter */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 text-zinc-500 font-mono text-xs">
            <Filter className="size-3.5 text-zinc-400" />
            <span className="hidden sm:inline">Wazuh Rule:</span>
          </div>
          {live ? (
            <input
              aria-label="Wazuh rule ID"
              value={selectedRuleId === 'ALL' ? '' : selectedRuleId}
              onChange={(event) => setSelectedRuleId(event.target.value)}
              placeholder="All rules"
              className="bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs font-mono text-zinc-200"
            />
          ) : <select
            aria-label="Wazuh rule ID"
            value={selectedRuleId}
            onChange={(e) => setSelectedRuleId(e.target.value)}
            className="bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs font-mono text-zinc-200 focus:outline-none focus:border-zinc-700 cursor-pointer"
          >
            <option value="ALL">All Monitored Rules</option>
            <option value="100201">Rule 100201 (Mimikatz Memory Dump)</option>
            <option value="100205">Rule 100205 (PowerShell Encoded)</option>
            <option value="100210">Rule 100210 (SSH Brute Force)</option>
            <option value="100220">Rule 100220 (Cron Persistence)</option>
            <option value="100230">Rule 100230 (Ransomware Shadow Copy)</option>
          </select>}
        </div>
      </div>

      {analytics?.report_window && (
        <p className="text-xs text-zinc-400">
          Reporting window {analytics.report_window.start_date} to {analytics.report_window.end_date} UTC.
          {analytics.audit_event_count != null && ` CSV includes all ${analytics.audit_event_count} audit events in this window and rule filter.`}
        </p>
      )}
      {isLoading && <p role="status" className="text-xs text-zinc-400">Loading analytics…</p>}

      {/* Error Banners */}
      {exportError && (
        <div role="alert" className="p-4 rounded-xl bg-red-950/40 border border-red-800/80 text-red-200 text-xs font-mono flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <AlertCircle className="size-4 text-red-400 shrink-0" />
            <span>{exportError}</span>
          </div>
          <button
            type="button"
            onClick={() => setExportError(null)}
            className="px-2.5 py-1 rounded bg-zinc-900 border border-zinc-750 text-xs text-zinc-300 hover:text-zinc-100 transition-colors"
          >
            Dismiss
          </button>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-xl bg-red-950/40 border border-red-800/80 text-red-200 text-xs font-mono flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <AlertCircle className="size-4 text-red-400 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={handleRefresh}
            className="px-3 py-1 rounded bg-red-900/60 border border-red-700 text-xs text-red-200 hover:bg-red-800 transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {/* KPI Summary Cards */}
      {analytics && <KpiSummaryGrid summary={analytics} isLoading={isLoading} />}

      {/* Main Longitudinal Trendline Chart */}
      {analytics && <OverrideTrendChart data={analytics.trendline} isLoading={isLoading} />}

      {/* Confusion Matrix & Guardrail Breakdown */}
      {analytics && <SeverityDeltaCard summary={analytics} isLoading={isLoading} />}

    </div>
  );
};
