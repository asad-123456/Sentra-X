import React, { useState, useEffect } from 'react';
import type { AlertListItem } from '../../types/sentrax';
import { SeverityBadge } from '../badges/SeverityBadge';
import { VerdictBadge } from '../badges/VerdictBadge';
import { ConfidenceMeter } from '../badges/ConfidenceMeter';
import { GuardrailBadges } from '../badges/GuardrailBadges';
import { AssetTierBadge } from '../badges/AssetTierBadge';
import { Check, ChevronRight, Inbox, Clock, RotateCcw } from 'lucide-react';

interface TriageQueueTableProps {
  alerts: AlertListItem[];
  isLoading: boolean;
  onSelectAlert: (alertId: string) => void;
  onQuickApprove: (alertId: string) => Promise<void>;
  hasActiveFilters: boolean;
  onResetFilters: () => void;
}

export const TriageQueueTable: React.FC<TriageQueueTableProps> = ({
  alerts,
  isLoading,
  onSelectAlert,
  onQuickApprove,
  hasActiveFilters,
  onResetFilters,
}) => {
  // Track which alert is in the 2-click confirm state
  const [confirmingAlertId, setConfirmingAlertId] = useState<string | null>(null);
  const [isApprovingId, setIsApprovingId] = useState<string | null>(null);

  // Auto-reset confirmation state after 4 seconds
  useEffect(() => {
    if (!confirmingAlertId) return;
    const timer = setTimeout(() => {
      setConfirmingAlertId(null);
    }, 4000);
    return () => clearTimeout(timer);
  }, [confirmingAlertId]);

  const handleQuickApproveClick = async (e: React.MouseEvent, alert: AlertListItem) => {
    e.stopPropagation();

    // Block automated approval if alert requires manual triage or analyst review
    if (
      alert.status !== 'AWAITING_ANALYST' ||
      alert.effective_verdict === 'NEEDS_MANUAL_TRIAGE' ||
      alert.effective_verdict === 'NEEDS_ANALYST_REVIEW'
    ) {
      return;
    }

    if (confirmingAlertId === alert.id) {

      // Second click: Execute approval
      setIsApprovingId(alert.id);
      try {
        await onQuickApprove(alert.id);
      } finally {
        setIsApprovingId(null);
        setConfirmingAlertId(null);
      }
    } else {
      // First click: Request confirmation
      setConfirmingAlertId(alert.id);
    }
  };

  const formatIngestedTime = (isoString: string) => {
    try {
      const date = new Date(isoString);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / (1000 * 60));
      if (diffMins < 1) return 'Just now';
      if (diffMins < 60) return `${diffMins}m ago`;
      const diffHours = Math.floor(diffMins / 60);
      if (diffHours < 24) return `${diffHours}h ago`;
      return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="bg-zinc-950 border border-zinc-800/80 rounded-xl overflow-hidden shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-zinc-800/80 text-[11px] font-mono text-zinc-400 bg-zinc-900/50">
              <th className="py-3 px-4 w-32 min-w-[120px]">SEVERITY</th>
              <th className="py-3 px-4 min-w-[300px]">RULE & THREAT DETAILS</th>
              <th className="py-3 px-4 w-44 min-w-[170px]">TARGET ASSET</th>
              <th className="py-3 px-4 w-40 min-w-[150px]">AI VERDICT</th>
              <th className="py-3 px-4 w-48 min-w-[180px]">CONFIDENCE</th>
              <th className="py-3 px-4 min-w-[240px]">ACTIVE GUARDRAILS</th>
              <th className="py-3 px-4 w-48 min-w-[180px] text-right">ACTIONS / INGESTED</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-900/80 text-xs font-mono">
            {isLoading ? (
              // High-fidelity shimmer skeleton rows matching exact column widths
              Array.from({ length: 5 }).map((_, idx) => (
                <tr key={idx} className="animate-pulse">
                  <td className="py-4 px-4 align-middle">
                    <div className="h-6 w-20 bg-zinc-800/60 rounded-md" />
                  </td>
                  <td className="py-4 px-4 align-middle space-y-2">
                    <div className="h-4 w-4/5 bg-zinc-800/60 rounded" />
                    <div className="h-3 w-1/2 bg-zinc-850/50 rounded" />
                  </td>
                  <td className="py-4 px-4 align-middle space-y-2">
                    <div className="h-4 w-28 bg-zinc-800/60 rounded" />
                    <div className="h-3 w-20 bg-zinc-850/50 rounded" />
                  </td>
                  <td className="py-4 px-4 align-middle">
                    <div className="h-6 w-24 bg-zinc-800/60 rounded-md" />
                  </td>
                  <td className="py-4 px-4 align-middle">
                    <div className="h-3 w-28 bg-zinc-800/60 rounded-full" />
                  </td>
                  <td className="py-4 px-4 align-middle">
                    <div className="h-5 w-36 bg-zinc-800/60 rounded-full" />
                  </td>
                  <td className="py-4 px-4 align-middle text-right">
                    <div className="h-7 w-20 bg-zinc-800/60 rounded-md ml-auto" />
                  </td>
                </tr>
              ))
            ) : alerts.length === 0 ? (
              // Empty State
              <tr>
                <td colSpan={7} className="py-16 px-4 text-center">
                  <div className="max-w-md mx-auto space-y-3">
                    <div className="p-3 bg-zinc-900 border border-zinc-800 rounded-full w-fit mx-auto text-zinc-400">
                      <Inbox className="size-6" />
                    </div>
                    <div className="space-y-1">
                      <div className="text-sm font-semibold text-zinc-200">
                        No alerts match the active filters
                      </div>
                      <div className="text-xs text-zinc-500 font-sans">
                        Try adjusting your search criteria, switching tabs, or resetting filters.
                      </div>
                    </div>
                    {hasActiveFilters && (
                      <button
                        type="button"
                        onClick={onResetFilters}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-zinc-900 hover:bg-zinc-800 border border-zinc-700/80 rounded-lg text-xs font-mono text-zinc-200 transition-colors cursor-pointer"
                      >
                        <RotateCcw className="size-3.5 text-zinc-400" />
                        <span>Reset All Filters</span>
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ) : (
              // Alerts Data Rows
              alerts.map((alert) => {
                const isManualTriage =
                  alert.status === 'NEEDS_MANUAL_TRIAGE' ||
                  alert.effective_verdict === 'NEEDS_MANUAL_TRIAGE';
                const isNeedsReview = alert.effective_verdict === 'NEEDS_ANALYST_REVIEW';
                const isConfirming = confirmingAlertId === alert.id;
                const isApproving = isApprovingId === alert.id;


                return (
                  <tr
                    key={alert.id}
                    onClick={() => onSelectAlert(alert.id)}
                    className="hover:bg-zinc-900/60 transition-colors cursor-pointer group"
                  >
                    {/* Column 1: Severity */}
                    <td className="py-3.5 px-4 align-middle">
                      <SeverityBadge
                        severity={alert.effective_severity}
                        safetyFloorUpgraded={alert.safety_floor_triggered}
                      />
                    </td>

                    {/* Column 2: Rule & Threat Details */}
                    <td className="py-3.5 px-4 align-middle">
                      <div className="font-semibold text-zinc-100 font-sans text-xs group-hover:text-zinc-50 transition-colors line-clamp-1">
                        {alert.rule_description}
                      </div>
                      <div className="text-[11px] text-zinc-400 mt-1 flex flex-wrap items-center gap-1.5">
                        <span className="text-zinc-300 font-mono">Rule {alert.rule_id}</span>
                        <span className="text-zinc-700">•</span>
                        <span>MITRE {alert.mitre_techniques.join(', ')}</span>
                      </div>
                      <div className="text-[11px] text-zinc-400 font-sans italic truncate max-w-md mt-1">
                        "{alert.truncated_explanation}"
                      </div>
                    </td>

                    {/* Column 3: Target Asset */}
                    <td className="py-3.5 px-4 align-middle">
                      <div className="space-y-1">
                        <div className="text-zinc-200 font-semibold text-xs font-mono">
                          {alert.agent_name}
                        </div>
                        <div className="text-[10px] text-zinc-400 font-mono flex items-center gap-1.5">
                          <span>{alert.src_ip || 'Internal'}</span>
                        </div>
                        <div>
                          <AssetTierBadge tier={alert.asset_criticality} />
                        </div>
                      </div>
                    </td>

                    {/* Column 4: AI Verdict */}
                    <td className="py-3.5 px-4 align-middle">
                      <VerdictBadge verdict={alert.effective_verdict} />
                    </td>

                    {/* Column 5: Confidence */}
                    <td className="py-3.5 px-4 align-middle">
                      <ConfidenceMeter score={alert.confidence_score} />
                    </td>

                    {/* Column 6: Active Guardrails */}
                    <td className="py-3.5 px-4 align-middle">
                      <GuardrailBadges
                        safetyFloorTriggered={alert.safety_floor_triggered}
                        abstentionTriggered={alert.abstention_triggered}
                        injectionSuspect={alert.injection_suspect}
                        hasFewShot={alert.has_few_shot}
                      />
                    </td>

                    {/* Column 7: Actions & Ingestion Timestamp */}
                    <td className="py-3.5 px-4 align-middle text-right">
                      <div className="flex flex-col items-end gap-1.5">
                        <div className="flex items-center gap-1 text-[11px] text-zinc-500 font-mono">
                          <Clock className="size-3" />
                          <span>{formatIngestedTime(alert.ingested_at)}</span>
                        </div>

                        <div className="flex items-center gap-1.5">
                          {/* 2-Click Quick Approve Button (Awaiting Analyst only) */}
                          {alert.status === 'AWAITING_ANALYST' && (
                            <button
                              type="button"
                              onClick={(e) => handleQuickApproveClick(e, alert)}
                              disabled={isManualTriage || isNeedsReview || isApproving}
                              title={
                                isManualTriage
                                  ? 'Manual review required — automated approval disabled'
                                  : isNeedsReview
                                  ? 'Abstention / Safety Floor active — inspect alert to select verdict'
                                  : isConfirming
                                  ? 'Click again to confirm approval'
                                  : 'Quick approve AI verdict directly from queue'
                              }
                              className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-mono font-medium transition-all ${
                                isManualTriage || isNeedsReview
                                  ? 'bg-zinc-900 text-zinc-600 border border-zinc-800 cursor-not-allowed opacity-60'
                                  : isConfirming
                                  ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-[0_0_10px_rgba(16,185,129,0.4)] animate-pulse'
                                  : 'bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-zinc-100 border border-zinc-800 hover:border-zinc-700'
                              }`}
                            >
                              <Check className={`size-3 ${isConfirming ? 'text-white' : 'text-emerald-400'}`} />
                              <span>{isApproving ? 'Saving...' : isConfirming ? 'Confirm?' : 'Approve'}</span>
                            </button>
                          )}


                          {/* Inspect Detail Trigger */}
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              onSelectAlert(alert.id);
                            }}
                            className="p-1 rounded-md text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 transition-colors"
                            title="Inspect alert details and evidence trace"
                          >
                            <ChevronRight className="size-4" />
                          </button>
                        </div>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

