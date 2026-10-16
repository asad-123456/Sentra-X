import React, { useState } from 'react';
import type {
  Alert,
  AIAssessment,
  UserRole,
  DecisionPayload,
  BinaryVerdict,
  SeverityLevel,
} from '../../types/sentrax';
import {
  Check,
  Edit3,
  Flame,
  RotateCcw,
  AlertCircle,
  X,
  BookmarkCheck,
  ShieldAlert,
  Sliders,
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
} from 'lucide-react';

interface DecisionActionPanelProps {
  alert: Alert;
  assessment: AIAssessment;
  userRole: UserRole;
  isSubmitting: boolean;
  onSubmitDecision: (payload: DecisionPayload) => Promise<void>;
  onCloseModal: () => void;
}

export const DecisionActionPanel: React.FC<DecisionActionPanelProps> = ({
  alert,
  assessment,
  userRole,
  isSubmitting,
  onSubmitDecision,
  onCloseModal,
}) => {
  // Mode toggle: 'none' | 'override' | 'manual_close' | 'resolve_escalation' | 'approve_prompt'
  const [panelMode, setPanelMode] = useState<
    'none' | 'override' | 'manual_close' | 'resolve_escalation' | 'approve_prompt'
  >('none');

  // Sub-tab for override/disposition workflow: 'parameters' | 'review'
  const [overrideTab, setOverrideTab] = useState<'parameters' | 'review'>('parameters');

  // Form states
  const [verdict, setVerdict] = useState<BinaryVerdict>(
    assessment.effective_verdict === 'FALSE_POSITIVE' ? 'FALSE_POSITIVE' : 'TRUE_POSITIVE'
  );
  const [severity, setSeverity] = useState<SeverityLevel>(assessment.effective_severity);
  const [rationale, setRationale] = useState<string>('');
  const [saveExemplar, setSaveExemplar] = useState<boolean>(true);
  const [validationError, setValidationError] = useState<string | null>(null);

  const resetForm = () => {
    setPanelMode('none');
    setOverrideTab('parameters');
    setRationale('');
    setValidationError(null);
  };

  const handleApproveClick = async () => {
    // If effective verdict is NEEDS_ANALYST_REVIEW, analyst must pick binary verdict first
    if (assessment.effective_verdict === 'NEEDS_ANALYST_REVIEW') {
      setPanelMode('approve_prompt');
      return;
    }

    // Direct approve
    await onSubmitDecision({
      alert_id: alert.id,
      action: 'APPROVE',
      final_verdict: assessment.effective_verdict === 'FALSE_POSITIVE' ? 'FALSE_POSITIVE' : 'TRUE_POSITIVE',
      final_severity: assessment.effective_severity,
      rationale: 'Accepted automated AI assessment recommendation.',
    });
  };

  const handleApproveWithVerdict = async (chosenVerdict: BinaryVerdict) => {
    await onSubmitDecision({
      alert_id: alert.id,
      action: 'APPROVE',
      final_verdict: chosenVerdict,
      final_severity: assessment.effective_severity,
      rationale: `Accepted assessment with confirmed ${chosenVerdict} disposition.`,
    });
  };

  const handleEscalateClick = async () => {
    await onSubmitDecision({
      alert_id: alert.id,
      action: 'ESCALATE',
      rationale: 'Escalated to SOC Team Lead for secondary evaluation and correlation review.',
    });
  };

  const handleRetryClick = async () => {
    await onSubmitDecision({
      alert_id: alert.id,
      action: 'RETRY_AI',
      rationale: 'Retrying automated LLM triage evaluation.',
    });
  };

  const handleProceedToReview = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (rationale.trim().length < 10) {
      setValidationError(
        'HTTP 422 Unprocessable Entity: Decision rationale must be at least 10 characters long before proceeding to Review Override.'
      );
      return;
    }
    setValidationError(null);
    setOverrideTab('review');
  };

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Rationale length validation
    if (rationale.trim().length < 10) {
      setValidationError(
        'HTTP 422 Unprocessable Entity: Decision rationale must be at least 10 characters long to provide an auditable justification.'
      );
      setOverrideTab('parameters');
      return;
    }

    if (overrideTab === 'parameters') {
      setValidationError(null);
      setOverrideTab('review');
      return;
    }

    setValidationError(null);

    let action: DecisionPayload['action'] = 'OVERRIDE';
    if (panelMode === 'manual_close') {
      action = 'MANUAL_TRIAGE_CLOSE';
    } else if (panelMode === 'resolve_escalation') {
      action = 'RESOLVE_ESCALATION';
    }

    await onSubmitDecision({
      alert_id: alert.id,
      action,
      final_verdict: verdict,
      final_severity: severity,
      rationale: rationale.trim(),
      save_as_exemplar: saveExemplar,
    });
  };

  const isClosed = alert.status === 'CLOSED';
  const isAwaiting = alert.status === 'AWAITING_ANALYST';
  const isNeedsManual = alert.status === 'NEEDS_MANUAL_TRIAGE';
  const isEscalated = alert.status === 'ESCALATED';
  const canResolveEscalation = isEscalated && (userRole === 'TeamLead' || userRole === 'Admin');

  return (
    <div className="border-t border-zinc-800 bg-zinc-950 p-4 shrink-0 space-y-4">
      {/* Inline Forms for Override, Manual Close, or Resolve Escalation */}
      {panelMode !== 'none' && panelMode !== 'approve_prompt' && (
        <form
          onSubmit={handleFormSubmit}
          className="p-4 rounded-xl bg-zinc-900/90 border border-zinc-700/80 space-y-4 animate-in fade-in slide-in-from-bottom-2"
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-zinc-800 pb-2.5">
            <div className="flex items-center gap-2">
              <Edit3 className="size-4 text-cyan-400" />
              <span className="font-mono font-bold text-zinc-100 text-xs">
                {panelMode === 'override' && 'Analyst Decision Override'}
                {panelMode === 'manual_close' && 'Manual Triage Disposition'}
                {panelMode === 'resolve_escalation' && 'Team Lead Escalation Resolution'}
              </span>
            </div>
            <button
              type="button"
              onClick={resetForm}
              className="text-zinc-400 hover:text-zinc-200 p-0.5 cursor-pointer"
              title="Cancel and close form"
            >
              <X className="size-4" />
            </button>
          </div>

          {/* 2-Stage Tabs: Configure vs Review Override */}
          <div className="flex items-center gap-2 border-b border-zinc-800/80 pb-2.5">
            <button
              type="button"
              onClick={() => setOverrideTab('parameters')}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-colors cursor-pointer ${
                overrideTab === 'parameters'
                  ? 'bg-zinc-800 text-zinc-100 border border-zinc-700 shadow-sm'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <Sliders className="size-3.5 text-zinc-400" />
              <span>Configure Parameters</span>
            </button>

            <button
              type="button"
              onClick={handleProceedToReview}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-colors cursor-pointer ${
                overrideTab === 'review'
                  ? 'bg-zinc-800 text-zinc-100 border border-zinc-700 shadow-sm'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <ShieldAlert className="size-3.5 text-amber-400" />
              <span>Review Override</span>
              {saveExemplar && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-950/80 text-amber-300 border border-amber-800/60 font-mono">
                  Poisoning Guard
                </span>
              )}
            </button>
          </div>

          {/* Validation Error Banner */}
          {validationError && (
            <div className="p-3 rounded-lg bg-red-950/60 border border-red-800 text-red-200 text-xs font-mono flex items-center gap-2">
              <AlertCircle className="size-4 text-red-400 shrink-0" />
              <span>{validationError}</span>
            </div>
          )}

          {/* Stage 1: Configure Parameters */}
          {overrideTab === 'parameters' && (
            <div className="space-y-4">
              {/* Verdict & Severity Pickers */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-[11px] font-mono text-zinc-400">FINAL VERDICT</label>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setVerdict('TRUE_POSITIVE')}
                      className={`py-2 px-3 rounded-lg text-xs font-mono font-bold transition-all cursor-pointer ${
                        verdict === 'TRUE_POSITIVE'
                          ? 'bg-red-950 text-red-200 border border-red-500 shadow-[0_0_10px_rgba(239,68,68,0.25)]'
                          : 'bg-zinc-950 text-zinc-400 border border-zinc-800 hover:text-zinc-200'
                      }`}
                    >
                      TRUE POSITIVE
                    </button>
                    <button
                      type="button"
                      onClick={() => setVerdict('FALSE_POSITIVE')}
                      className={`py-2 px-3 rounded-lg text-xs font-mono font-bold transition-all cursor-pointer ${
                        verdict === 'FALSE_POSITIVE'
                          ? 'bg-emerald-950 text-emerald-200 border border-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.25)]'
                          : 'bg-zinc-950 text-zinc-400 border border-zinc-800 hover:text-zinc-200'
                      }`}
                    >
                      FALSE POSITIVE
                    </button>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-[11px] font-mono text-zinc-400">FINAL SEVERITY</label>
                  <select
                    value={severity}
                    onChange={(e) => setSeverity(e.target.value as SeverityLevel)}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs font-mono text-zinc-100 focus:outline-none focus:border-zinc-600 cursor-pointer"
                  >
                    <option value="CRITICAL">CRITICAL (12–15)</option>
                    <option value="HIGH">HIGH (8–11)</option>
                    <option value="MEDIUM">MEDIUM (4–7)</option>
                    <option value="LOW">LOW (0–3)</option>
                  </select>
                </div>
              </div>

              {/* Rationale Textarea */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-[11px] font-mono">
                  <label className="text-zinc-300">
                    AUDIT RATIONALE <span className="text-red-400">*</span>
                  </label>
                  <span
                    className={`text-[10px] ${
                      rationale.trim().length >= 10 ? 'text-emerald-400 font-bold' : 'text-zinc-500'
                    }`}
                  >
                    {rationale.trim().length} / 10 min chars
                  </span>
                </div>
                <textarea
                  value={rationale}
                  onChange={(e) => {
                    setRationale(e.target.value);
                    if (validationError && e.target.value.trim().length >= 10) {
                      setValidationError(null);
                    }
                  }}
                  rows={3}
                  placeholder="State the technical justification for this decision (e.g., verified change ticket, legitimate admin tool, or confirmed credential dumping)..."
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-3 text-xs font-sans text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-600 transition-colors custom-scrollbar resize-y min-h-[90px]"
                />
              </div>

              {/* Checkbox: Save as Few-Shot Exemplar */}
              <label className="flex items-center gap-2 cursor-pointer select-none text-xs text-zinc-300 font-sans">
                <input
                  type="checkbox"
                  checked={saveExemplar}
                  onChange={(e) => setSaveExemplar(e.target.checked)}
                  className="size-4 rounded border-zinc-700 bg-zinc-950 text-cyan-500 focus:ring-0 focus:ring-offset-0 cursor-pointer"
                />
                <div className="flex items-center gap-1.5">
                  <BookmarkCheck className="size-3.5 text-cyan-400" />
                  <span>Register as feedback calibration exemplar for future prompt matching</span>
                </div>
              </label>

              {/* Parameters Stage Action Buttons */}
              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={resetForm}
                  className="px-4 py-2 rounded-lg bg-zinc-950 hover:bg-zinc-800 border border-zinc-800 text-xs font-mono text-zinc-300 transition-colors cursor-pointer"
                >
                  Cancel
                </button>

                <button
                  type="button"
                  onClick={handleProceedToReview}
                  className="flex items-center gap-2 px-5 py-2 rounded-lg bg-white hover:bg-zinc-200 text-black font-mono font-bold text-xs shadow-md transition-all cursor-pointer"
                >
                  <span>Review Override</span>
                  <ArrowRight className="size-3.5" />
                </button>
              </div>
            </div>
          )}

          {/* Stage 2: Review Override (Feedback Poisoning Guard) */}
          {overrideTab === 'review' && (
            <div className="space-y-4">
              {/* Feedback Poisoning Guard Warning */}
              <div className="p-3.5 rounded-xl bg-amber-950/30 border border-amber-700/60 text-amber-200 text-xs font-sans space-y-1">
                <div className="font-semibold text-amber-300 flex items-center gap-2 font-mono text-xs">
                  <ShieldAlert className="size-4 text-amber-400 shrink-0" />
                  <span>Feedback Poisoning Prevention Gate</span>
                </div>
                <p className="text-[11px] text-zinc-300 leading-relaxed font-sans">
                  Please verify your override disposition and rationale before final commit. Erroneous verdicts or inaccurate rationales directly contaminate the few-shot calibration catalog for future LLM triage queries.
                </p>
              </div>

              {/* Side-by-side comparison */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 p-3.5 rounded-xl bg-zinc-950 border border-zinc-800">
                {/* Current Assessment */}
                <div className="space-y-2 p-3 rounded-lg bg-zinc-900/60 border border-zinc-850">
                  <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider">Current AI Assessment</span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-bold text-zinc-300">{assessment.effective_verdict}</span>
                    <span className="text-zinc-600">•</span>
                    <span className="text-xs font-mono font-semibold text-zinc-400">{assessment.effective_severity}</span>
                  </div>
                  <div className="text-[11px] text-zinc-500 font-sans line-clamp-2">
                    {assessment.explanation}
                  </div>
                </div>

                {/* Proposed Override */}
                <div className="space-y-2 p-3 rounded-lg bg-zinc-900 border border-cyan-800/60">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-mono text-cyan-400 uppercase tracking-wider font-semibold">
                      Proposed Analyst Override
                    </span>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-700/80">
                      {verdict === assessment.effective_verdict ? 'Severity Adjustment' : 'Verdict Flip'}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-mono font-bold ${verdict === 'TRUE_POSITIVE' ? 'text-red-400' : 'text-emerald-400'}`}>
                      {verdict}
                    </span>
                    <span className="text-zinc-600">•</span>
                    <span className="text-xs font-mono font-bold text-zinc-100">{severity}</span>
                  </div>
                  <div className="text-[11px] text-zinc-400 font-mono">
                    Target: Rule {alert.rule_id} • {alert.agent_name}
                  </div>
                </div>
              </div>

              {/* Documented Audit Rationale Card */}
              <div className="space-y-1.5 p-3.5 rounded-xl bg-zinc-950 border border-zinc-800">
                <div className="flex items-center justify-between text-[11px] font-mono text-zinc-400">
                  <span>DOCUMENTED AUDIT RATIONALE</span>
                  <span className="text-emerald-400 font-semibold">{rationale.trim().length} characters</span>
                </div>
                <div className="p-3 rounded-lg bg-zinc-900/80 border border-zinc-800 text-xs font-mono text-zinc-200 whitespace-pre-wrap leading-relaxed select-text">
                  {rationale.trim()}
                </div>
              </div>

              {/* Exemplar Indexing Status */}
              <div className="flex items-center justify-between px-3.5 py-2.5 rounded-xl bg-zinc-950 border border-zinc-800 text-xs font-mono">
                <div className="flex items-center gap-2">
                  <BookmarkCheck className={`size-4 ${saveExemplar ? 'text-cyan-400' : 'text-zinc-600'}`} />
                  <span className={saveExemplar ? 'text-zinc-200' : 'text-zinc-500'}>
                    {saveExemplar
                      ? 'Exemplar Calibration: Enabled (Will be indexed as authoritative few-shot pattern)'
                      : 'Exemplar Calibration: Disabled (Audit log update only, no prompt exemplar)'}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setSaveExemplar(!saveExemplar)}
                  className="text-[11px] text-cyan-400 hover:text-cyan-300 underline cursor-pointer"
                >
                  Change
                </button>
              </div>

              {/* Review Stage Action Buttons */}
              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setOverrideTab('parameters')}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-zinc-950 hover:bg-zinc-800 border border-zinc-800 text-xs font-mono text-zinc-300 transition-colors cursor-pointer"
                >
                  <ArrowLeft className="size-3.5" />
                  <span>Back to Parameters</span>
                </button>

                <button
                  type="button"
                  onClick={resetForm}
                  className="px-4 py-2 rounded-lg bg-zinc-950 hover:bg-zinc-800 border border-zinc-800 text-xs font-mono text-zinc-300 transition-colors cursor-pointer"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="flex items-center gap-2 px-5 py-2 rounded-lg bg-white hover:bg-zinc-200 text-black font-mono font-bold text-xs shadow-md transition-all cursor-pointer disabled:opacity-50"
                >
                  <CheckCircle2 className="size-3.5 text-emerald-600" />
                  <span>{isSubmitting ? 'Committing...' : 'Confirm & Commit Override'}</span>
                </button>
              </div>
            </div>
          )}
        </form>
      )}

      {/* Approve Prompt Modal (when effective verdict is NEEDS_ANALYST_REVIEW) */}
      {panelMode === 'approve_prompt' && (
        <div className="p-4 rounded-xl bg-zinc-900 border border-cyan-800/80 space-y-3 animate-in fade-in">
          <div className="flex items-center justify-between">
            <div className="text-zinc-200 font-mono font-bold text-xs flex items-center gap-2">
              <ShieldAlert className="size-4 text-cyan-400" />
              <span>Select Final Binary Disposition</span>
            </div>
            <button
              type="button"
              onClick={resetForm}
              className="text-zinc-400 hover:text-zinc-200 p-0.5"
            >
              <X className="size-4" />
            </button>
          </div>

          <p className="text-xs text-zinc-400 font-sans">
            The automated triage flagged this alert for analyst review. Choose the authoritative disposition to commit approval:
          </p>

          <div className="flex items-center justify-end gap-3 pt-1">
            <button
              type="button"
              onClick={() => handleApproveWithVerdict('FALSE_POSITIVE')}
              disabled={isSubmitting}
              className="px-4 py-2 rounded-lg bg-emerald-950 hover:bg-emerald-900 border border-emerald-700 text-emerald-200 text-xs font-mono font-bold transition-colors cursor-pointer"
            >
              Approve as FALSE POSITIVE
            </button>
            <button
              type="button"
              onClick={() => handleApproveWithVerdict('TRUE_POSITIVE')}
              disabled={isSubmitting}
              className="px-4 py-2 rounded-lg bg-red-950 hover:bg-red-900 border border-red-700 text-red-200 text-xs font-mono font-bold transition-colors cursor-pointer"
            >
              Approve as TRUE POSITIVE
            </button>
          </div>
        </div>
      )}

      {/* Main Bottom Toolbar */}
      {panelMode === 'none' && (
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="text-xs font-mono text-zinc-500">
            {isClosed ? (
              <span className="text-zinc-400">Status: Terminal closed in immutable audit log</span>
            ) : isEscalated ? (
              <span className="text-amber-400">Status: Escalated for Tier-2 / Lead review</span>
            ) : isNeedsManual ? (
              <span className="text-purple-400">Status: Automated triage exhausted — manual decision required</span>
            ) : (
              <span className="text-zinc-300">Status: Actionable analyst review required</span>
            )}
          </div>

          {/* Action Button Groups */}
          <div className="flex items-center gap-2.5">
            {/* Close Modal Button */}
            <button
              type="button"
              onClick={onCloseModal}
              className="px-4 py-2 rounded-lg bg-zinc-900 hover:bg-zinc-850 border border-zinc-800 text-xs font-mono text-zinc-300 hover:text-white transition-colors"
            >
              Close
            </button>

            {/* AWAITING_ANALYST Actions */}
            {isAwaiting && (
              <>
                <button
                  type="button"
                  onClick={handleEscalateClick}
                  disabled={isSubmitting}
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-amber-950/60 hover:bg-amber-900/60 border border-amber-800/80 text-amber-200 text-xs font-mono font-medium transition-colors"
                >
                  <Flame className="size-3.5 text-amber-400" />
                  <span>Escalate</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setPanelMode('override');
                    setOverrideTab('parameters');
                  }}
                  disabled={isSubmitting}
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 text-zinc-200 text-xs font-mono font-semibold transition-colors cursor-pointer"
                >
                  <Edit3 className="size-3.5 text-zinc-400" />
                  <span>Override Decision</span>
                </button>

                <button
                  type="button"
                  onClick={handleApproveClick}
                  disabled={isSubmitting}
                  className="flex items-center gap-1.5 px-5 py-2 rounded-lg bg-white hover:bg-zinc-200 text-black text-xs font-mono font-bold shadow-md transition-all cursor-pointer"
                >
                  <Check className="size-4 text-emerald-600" />
                  <span>Approve Assessment</span>
                </button>
              </>
            )}

            {/* NEEDS_MANUAL_TRIAGE Actions */}
            {isNeedsManual && (
              <>
                <button
                  type="button"
                  onClick={handleRetryClick}
                  disabled={isSubmitting}
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 text-zinc-200 text-xs font-mono font-medium transition-colors cursor-pointer"
                >
                  <RotateCcw className="size-3.5 text-zinc-400" />
                  <span>Retry AI Triage</span>
                </button>

                <button
                  type="button"
                  onClick={handleEscalateClick}
                  disabled={isSubmitting}
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-amber-950/60 hover:bg-amber-900/60 border border-amber-800/80 text-amber-200 text-xs font-mono font-medium transition-colors cursor-pointer"
                >
                  <Flame className="size-3.5 text-amber-400" />
                  <span>Escalate</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setPanelMode('manual_close');
                    setOverrideTab('parameters');
                  }}
                  disabled={isSubmitting}
                  className="flex items-center gap-1.5 px-5 py-2 rounded-lg bg-white hover:bg-zinc-200 text-black text-xs font-mono font-bold shadow-md transition-all cursor-pointer"
                >
                  <Check className="size-4 text-purple-600" />
                  <span>Manual Disposition</span>
                </button>
              </>
            )}

            {/* ESCALATED Actions */}
            {isEscalated && (
              <>
                {canResolveEscalation ? (
                  <button
                    type="button"
                    onClick={() => {
                      setPanelMode('resolve_escalation');
                      setOverrideTab('parameters');
                    }}
                    disabled={isSubmitting}
                    className="flex items-center gap-1.5 px-5 py-2 rounded-lg bg-white hover:bg-zinc-200 text-black text-xs font-mono font-bold shadow-md transition-all cursor-pointer"
                  >
                    <Check className="size-4 text-amber-600" />
                    <span>Resolve Escalation</span>
                  </button>
                ) : (
                  <span className="text-[11px] font-mono text-zinc-500 italic">
                    Requires Team Lead or Admin role to resolve
                  </span>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
