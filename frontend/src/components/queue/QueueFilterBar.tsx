import type { QueueTab, GuardrailFilter, QueueCounts } from '../../types/sentrax';
import { Button } from '../ui/button';

interface QueueFilterBarProps {
  currentTab: QueueTab;
  onTabChange: (tab: QueueTab) => void;
  subStatus: string;
  onSubStatusChange: (status: string) => void;
  search: string;
  onSearchChange: (search: string) => void;
  ruleId: string;
  onRuleIdChange: (ruleId: string) => void;
  severity: string;
  onSeverityChange: (severity: string) => void;
  guardrail: GuardrailFilter;
  onGuardrailChange: (guardrail: GuardrailFilter) => void;
  assetTier: string;
  onAssetTierChange: (assetTier: string) => void;
  counts: QueueCounts;
  onResetFilters: () => void;
  hasActiveFilters: boolean;
}

export function QueueFilterBar({
  currentTab, onTabChange, subStatus, onSubStatusChange, search, onSearchChange,
  ruleId, onRuleIdChange, severity, onSeverityChange, guardrail, onGuardrailChange,
  assetTier, onAssetTierChange, counts, onResetFilters, hasActiveFilters,
}: QueueFilterBarProps) {
  const views: { id: QueueTab; label: string; count: number }[] = [
    { id: 'awaiting', label: 'Review', count: counts.awaiting },
    { id: 'escalated', label: 'Escalated', count: counts.escalated },
    { id: 'closed', label: 'Closed audit log', count: counts.closed },
  ];
  const advancedCount = [ruleId.trim() !== '', severity !== 'ALL', guardrail !== 'ALL', assetTier !== 'ALL'].filter(Boolean).length;

  return (
    <section aria-label="Queue views and filters" className="surface p-3 sm:p-4">
      <div className="flex flex-wrap items-center gap-2 border-b border-border pb-3" role="group" aria-label="Queue view">
        {views.map(({ id, label, count }) => (
          <Button key={id} type="button" variant={currentTab === id ? 'secondary' : 'ghost'}
            className="min-h-9 px-2.5 sm:px-3" aria-pressed={currentTab === id} onClick={() => onTabChange(id)}>
            {label} <span className="text-xs tabular-nums text-muted-foreground">{count}</span>
          </Button>
        ))}
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label className="grid min-w-0 gap-1 text-xs font-medium text-muted-foreground">
          Search alerts
          <input className="field" type="search" value={search} onChange={(event) => onSearchChange(event.target.value)} placeholder="Rule, hostname, IP, or alert ID" />
        </label>
        {currentTab === 'awaiting' && (
          <label className="grid min-w-0 gap-1 text-xs font-medium text-muted-foreground">
            Review state
            <select className="field" value={subStatus} onChange={(event) => onSubStatusChange(event.target.value)}>
              <option value="ALL">All actionable ({counts.awaiting})</option>
              <option value="AWAITING_ANALYST">Model assessment ready ({counts.awaitingAnalystCount})</option>
              <option value="NEEDS_MANUAL_TRIAGE">Manual triage required ({counts.needsManualTriageCount})</option>
            </select>
          </label>
        )}
      </div>
      <details className="mt-2">
        <summary className="cursor-pointer rounded-sm py-2 text-sm font-medium">More filters{advancedCount > 0 && ` (${advancedCount} active)`}</summary>
        <div className="grid gap-3 py-2 sm:grid-cols-2 xl:grid-cols-4">
        <label className="grid min-w-0 gap-1 text-xs font-medium text-muted-foreground">
          Wazuh rule ID
          <input className="field" type="search" value={ruleId} onChange={(event) => onRuleIdChange(event.target.value)} placeholder="All rules" />
        </label>
        <label className="grid min-w-0 gap-1 text-xs font-medium text-muted-foreground">
          Severity
          <select className="field" value={severity} onChange={(event) => onSeverityChange(event.target.value)}>
            <option value="ALL">All severities</option>
            <option value="CRITICAL">Critical (12–15)</option>
            <option value="HIGH">High (8–11)</option>
            <option value="MEDIUM">Medium (4–7)</option>
            <option value="LOW">Low (0–3)</option>
          </select>
        </label>
        <label className="grid min-w-0 gap-1 text-xs font-medium text-muted-foreground">
          Guardrail
          <select className="field" value={guardrail} onChange={(event) => onGuardrailChange(event.target.value as GuardrailFilter)}>
            <option value="ALL">All guardrail states</option>
            <option value="SAFETY_FLOOR">Safety floor enforced</option>
            <option value="ABSTENTION">Model deferred</option>
            <option value="INJECTION_SUSPECT">Injection suspected</option>
            <option value="MANUAL_TRIAGE">Manual triage required</option>
          </select>
        </label>
        <label className="grid min-w-0 gap-1 text-xs font-medium text-muted-foreground">
          Asset criticality
          <select className="field" value={assetTier} onChange={(event) => onAssetTierChange(event.target.value)}>
            <option value="ALL">All tiers</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
          </select>
        </label>
        </div>
      </details>
      {hasActiveFilters && <Button variant="ghost" type="button" className="mt-2" onClick={onResetFilters}>Reset filters</Button>}
    </section>
  );
}
