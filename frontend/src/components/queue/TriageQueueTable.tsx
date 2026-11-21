import { useEffect, useState } from 'react';
import type { AlertListItem } from '../../types/sentrax';
import { SeverityBadge } from '../badges/SeverityBadge';
import { VerdictBadge } from '../badges/VerdictBadge';
import { GuardrailBadges } from '../badges/GuardrailBadges';
import { Button } from '../ui/button';

interface TriageQueueTableProps {
  alerts: AlertListItem[];
  isLoading: boolean;
  onSelectAlert: (alertId: string, opener: HTMLButtonElement) => void;
  onQuickApprove: (alertId: string) => Promise<void>;
  hasActiveFilters: boolean;
  onResetFilters: () => void;
}

const STATUS_LABELS: Record<AlertListItem['status'], string> = {
  PENDING_REVIEW: 'Assessment pending',
  AWAITING_ANALYST: 'Assessment ready',
  NEEDS_MANUAL_TRIAGE: 'Manual triage required',
  ESCALATED: 'Escalated',
  CLOSED: 'Closed',
};

function canQuickApprove(alert: AlertListItem): boolean {
  return !!alert.available_actions?.includes('APPROVE') && !alert.abstention_triggered &&
    (alert.effective_verdict === 'TRUE_POSITIVE' || alert.effective_verdict === 'FALSE_POSITIVE');
}

export function TriageQueueTable({
  alerts, isLoading, onSelectAlert, onQuickApprove, hasActiveFilters, onResetFilters,
}: TriageQueueTableProps) {
  const [confirming, setConfirming] = useState<string | null>(null);
  const [approving, setApproving] = useState<string | null>(null);

  useEffect(() => {
    if (!confirming) return;
    const timer = setTimeout(() => setConfirming(null), 4000);
    return () => clearTimeout(timer);
  }, [confirming]);

  async function approve(alert: AlertListItem) {
    if (approving || isLoading || !canQuickApprove(alert)) return;
    if (confirming !== alert.id) {
      setConfirming(alert.id);
      return;
    }
    setApproving(alert.id);
    try {
      await onQuickApprove(alert.id);
    } finally {
      setApproving(null);
      setConfirming(null);
    }
  }

  if (!alerts.length) {
    return (
      <div className="surface grid justify-items-center gap-2 p-8 text-center" aria-busy={isLoading}>
        <p role="status" className="font-semibold">
          {isLoading ? 'Loading alerts…' : hasActiveFilters ? 'No alerts match these filters' : 'No alerts in this view'}
        </p>
        {!isLoading && hasActiveFilters && (
          <>
            <p className="text-sm text-muted-foreground">Clear the filters to see more alerts.</p>
            <Button variant="outline" onClick={onResetFilters}>Reset filters</Button>
          </>
        )}
      </div>
    );
  }

  return (
    <div className="surface min-w-0" aria-busy={isLoading}>
      <table className="w-full table-fixed text-left text-sm">
        <caption className="sr-only">Alerts in the current queue view</caption>
        <thead>
          <tr className="border-b border-border text-xs text-muted-foreground">
            <th scope="col" className="hidden w-28 px-3 py-3 md:table-cell">Severity</th>
            <th scope="col" className="px-3 py-3">Alert</th>
            <th scope="col" className="hidden w-36 px-3 py-3 lg:table-cell">Host</th>
            <th scope="col" className="hidden w-40 px-3 py-3 md:table-cell">Review state</th>
            <th scope="col" className="w-27 px-2 py-3 text-right sm:w-36 sm:px-3">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {alerts.map((alert) => (
            <tr key={alert.id} className="align-top hover:bg-muted/35 focus-within:bg-muted/35">
              <td className="hidden px-3 py-4 md:table-cell">
                {alert.effective_severity ? <SeverityBadge severity={alert.effective_severity} safetyFloorUpgraded={alert.safety_floor_triggered} /> : 'Pending'}
              </td>
              <th scope="row" className="min-w-0 px-3 py-3 font-normal [overflow-wrap:anywhere]">
                <div className="mb-1 flex flex-wrap items-center gap-1 md:hidden">
                  {alert.effective_severity && <SeverityBadge severity={alert.effective_severity} safetyFloorUpgraded={alert.safety_floor_triggered} />}
                  <span className="text-xs text-muted-foreground">{STATUS_LABELS[alert.status]}</span>
                </div>
                <span className="font-semibold leading-snug">{alert.rule_description}</span>
                <p className="mt-1 text-xs text-muted-foreground">
                  <span className="font-mono">Rule {alert.rule_id}</span>
                  <span className="lg:hidden"> · {alert.agent_name}</span>
                </p>
                <p className="mt-1 hidden text-xs text-muted-foreground sm:line-clamp-2">
                  {alert.explanation_snippet || alert.truncated_explanation}
                </p>
                {(alert.safety_floor_triggered || alert.abstention_triggered || alert.injection_suspect || alert.has_few_shot) && (
                  <div className="mt-2 hidden xl:block">
                    <GuardrailBadges safetyFloorTriggered={alert.safety_floor_triggered}
                      abstentionTriggered={alert.abstention_triggered} injectionSuspect={alert.injection_suspect}
                      hasFewShot={alert.has_few_shot} className="flex-wrap whitespace-normal" />
                  </div>
                )}
              </th>
              <td className="hidden px-3 py-3 [overflow-wrap:anywhere] lg:table-cell">
                <p className="font-medium">{alert.agent_name}</p>
                <p className="mb-1 text-xs text-muted-foreground">{alert.src_ip || 'Internal'}</p>
                <p className="text-xs text-muted-foreground">{alert.asset_criticality ? `Asset: ${alert.asset_criticality.toLowerCase()}` : 'Asset tier unknown'}</p>
              </td>
              <td className="hidden px-3 py-3 md:table-cell">
                <span>{STATUS_LABELS[alert.status]}</span>
                {alert.effective_verdict && (
                  <div className="mt-1"><VerdictBadge verdict={alert.effective_verdict} /></div>
                )}
                {alert.confidence_score != null && <p className="mt-1 text-xs text-muted-foreground">{Math.round(alert.confidence_score * 100)}% confidence</p>}
              </td>
              <td className="px-2 py-2 text-right sm:px-3">
                <div className="flex flex-col items-end gap-1">
                  <Button type="button" variant="outline" className="h-11 px-2 text-xs sm:px-3 sm:text-sm"
                    aria-label={'Open alert: ' + alert.rule_description}
                    title="Open alert and inspect evidence"
                    onClick={(event) => onSelectAlert(alert.id, event.currentTarget)}>
                    Open alert
                  </Button>
                  {canQuickApprove(alert) && (
                    <Button type="button" variant={confirming === alert.id ? 'default' : 'ghost'}
                      size="sm" className="min-h-8 max-w-full whitespace-normal px-1 text-xs sm:px-2"
                      aria-label={(confirming === alert.id ? 'Confirm approval: ' : 'Quick approve: ') + alert.rule_description}
                      disabled={isLoading || approving !== null} onClick={() => void approve(alert)}>
                      {approving === alert.id ? 'Saving…' : confirming === alert.id ? 'Confirm approval' : 'Quick approve'}
                    </Button>
                  )}
                  <time className="hidden text-xs text-muted-foreground xl:block" dateTime={alert.ingested_at}>
                    {new Date(alert.ingested_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                  </time>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
