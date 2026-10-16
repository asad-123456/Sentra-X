import React, { useState, useEffect } from 'react';
import type { AnalyticsSummary } from '../types/sentrax';
import { getAnalytics, exportAuditCsv } from '../api/services';
import { KpiSummaryGrid } from '../components/analytics/KpiSummaryGrid';
import { OverrideTrendChart } from '../components/analytics/OverrideTrendChart';
import { SeverityDeltaCard } from '../components/analytics/SeverityDeltaCard';
import {
  Download,
  RotateCcw,
  Sparkles,
  Check,
  AlertCircle,
  Calendar,
  Filter,
} from 'lucide-react';

export const TeamLeadAnalyticsView: React.FC = () => {
  const [dateRange, setDateRange] = useState<string>('30d');
  const [selectedRuleId, setSelectedRuleId] = useState<string>('ALL');
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [exportSuccess, setExportSuccess] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleRefresh = () => {
    setIsLoading(true);
    setError(null);
    getAnalytics(dateRange, selectedRuleId)
      .then((data) => {
        setAnalytics(data);
        setIsLoading(false);
      })
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : 'Analytics data could not be retrieved.';
        setError(message);
        setIsLoading(false);
      });
  };

  useEffect(() => {
    let isCancelled = false;

    getAnalytics(dateRange, selectedRuleId)
      .then((data) => {
        if (!isCancelled) {
          setAnalytics(data);
          setIsLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!isCancelled) {
          const message = err instanceof Error ? err.message : 'Analytics data could not be retrieved.';
          setError(message);
          setIsLoading(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [dateRange, selectedRuleId]);

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const csvData = await exportAuditCsv();
      const blob = new Blob([csvData], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const today = new Date().toISOString().slice(0, 10);
      link.setAttribute('download', `sentrax_audit_trail_${today}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);

      setExportSuccess(true);
      setTimeout(() => setExportSuccess(false), 3000);
    } catch (err) {
      console.error('CSV Export failed:', err);
      alert('Failed to generate audit CSV export.');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* View Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-xl font-bold tracking-tight text-zinc-50 font-mono">
            Triage Analytics &amp; Calibration
          </h1>
          <p className="text-xs text-zinc-400 font-sans">
            Analyst agreement metrics, override frequency, and audit logs.
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
            disabled={isExporting}
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
              { id: 'all', label: 'All Time' },
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

        {/* Rule Filter Dropdown */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 text-zinc-500 font-mono text-xs">
            <Filter className="size-3.5 text-zinc-400" />
            <span className="hidden sm:inline">Wazuh Rule:</span>
          </div>
          <select
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
          </select>
        </div>
      </div>

      {/* Error Banner */}
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

      {/* Calibration Insight Card */}
      <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-850 flex items-start gap-3.5">
        <div className="p-2 rounded-lg bg-cyan-950/60 border border-cyan-800/60 text-cyan-400 shrink-0 mt-0.5">
          <Sparkles className="size-4" />
        </div>
        <div className="space-y-1">
          <div className="text-xs font-mono font-bold text-zinc-200">
            Dynamic Few-Shot Feedback Calibration
          </div>
          <p className="text-xs text-zinc-400 font-sans leading-relaxed">
            As SOC analysts override decisions, active exemplars are indexed into the database and injected into future prompt retrievals for the matching rule and process signature. Over successive operating cycles, repeat human overrides decline significantly without requiring model weight fine-tuning.
          </p>
        </div>
      </div>
    </div>
  );
};
