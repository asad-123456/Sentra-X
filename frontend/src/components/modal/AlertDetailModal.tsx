import React, { useState, useEffect, useRef } from 'react';
import type { AlertDetail, DecisionPayload } from '../../types/sentrax';
import { getAlertDetail, submitDecision } from '../../api/services';
import { useAuth } from '../../context/AuthContext';
import { AssessmentPane } from './AssessmentPane';
import { EvidenceTreePane } from './EvidenceTreePane';
import { DecisionActionPanel } from './DecisionActionPanel';
import { AssetTierBadge } from '../badges/AssetTierBadge';
import { Dialog, DialogContent, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import {
  X,
  Clock,
  Terminal,
  Shield,
  Loader2,
  AlertCircle,
} from 'lucide-react';

interface AlertDetailModalProps {
  alertId: string;
  opener: HTMLButtonElement;
  onClose: () => void;
  onDecisionCommitted: (message: string) => void;
}

export const AlertDetailModal: React.FC<AlertDetailModalProps> = ({
  alertId,
  opener,
  onClose,
  onDecisionCommitted,
}) => {
  const { user } = useAuth();
  const [detail, setDetail] = useState<AlertDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [citation, setCitation] = useState<{ key: string } | null>(null);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [savedAuditId, setSavedAuditId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [mobilePane, setMobilePane] = useState<'assessment' | 'evidence'>('assessment');
  const title = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    getAlertDetail(alertId, controller.signal, user?.role)
      .then((data) => {
        if (!controller.signal.aborted) setDetail(data);
      })
      .catch((err: unknown) => {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : 'Alert detail could not be retrieved.');
        }
      });
    return () => controller.abort();
  }, [alertId, refreshVersion, user?.role]);

  const returnFocus = () => opener.isConnected ? opener : document.getElementById('triage-queue-title');
  const close = () => {
    onClose();
    requestAnimationFrame(() => returnFocus()?.focus());
  };

  const refreshDetail = () => {
    setDetail(null);
    setError(null);
    setSubmitError(null);
    setCitation(null);
    setRefreshVersion((version) => version + 1);
  };

  // Handle decision submission
  const handleSubmitDecision = async (payload: DecisionPayload) => {
    if (!user || isSubmitting) return;
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const audit = await submitDecision(payload, user);
      setSavedAuditId(audit.id);
      setMobilePane('assessment');
      refreshDetail();
      onDecisionCommitted(`Decision saved. Audit #${audit.id.slice(-6)}.`);
    } catch (err: unknown) {
      console.error('Error submitting decision:', err);
      const message = err instanceof Error ? err.message : 'Failed to submit decision.';
      setSubmitError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const assetTier = detail?.evidence_pack?.asset_context?.criticality_tier ?? detail?.asset?.criticality_tier;
  const auditTrail = detail?.decision_audit_trail ?? detail?.audit_trail;

  return (
    <Dialog open onOpenChange={(open) => { if (!open) close(); }} disablePointerDismissal>
      <DialogContent showCloseButton={false} initialFocus={title} finalFocus={returnFocus}
        className="flex h-dvh max-w-full flex-col gap-0 overflow-hidden rounded-none border border-border bg-background p-0 sm:h-[92dvh] sm:max-w-[min(80rem,calc(100%-2rem))] sm:rounded-xl">
        <DialogTitle ref={title} tabIndex={-1} className="sr-only">
          {detail ? `Alert details: ${detail.alert.rule_description}` : 'Alert details'}
        </DialogTitle>
        {savedAuditId && (
          <div role="status" className="shrink-0 border-b border-emerald-900 bg-emerald-950/40 px-5 py-2 text-xs text-emerald-200">
            Decision saved. Audit #{savedAuditId.slice(-6)}.
          </div>
        )}
        {/* Loading State */}
        {!detail && !error && (
          <div role="status" className="flex-1 flex flex-col items-center justify-center gap-3 text-zinc-400 font-mono text-xs">
            <Loader2 className="size-6 text-cyan-400 animate-spin" />
            <span>Loading telemetry evidence pack &amp; model assessment...</span>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div role="alert" className="flex-1 flex flex-col items-center justify-center gap-4 p-6 text-center">
            <div className="p-3 bg-red-950/60 border border-red-800 rounded-full text-red-400">
              <AlertCircle className="size-6" />
            </div>
            <div className="space-y-1">
              <div className="text-sm font-semibold text-zinc-100 font-mono">Failed to Load Alert</div>
              <div className="text-xs text-zinc-400 font-sans max-w-md">{error}</div>
            </div>
            <div className="flex gap-3">
              <button type="button" onClick={refreshDetail} className="rounded border border-zinc-700 px-4 py-2 text-xs text-zinc-100">Retry alert</button>
                <Button type="button" onClick={close} variant="outline">Close alert</Button>
            </div>
          </div>
        )}

        {/* Loaded Detail Modal */}
        {detail && !error && (
          <>
            {/* Modal Header */}
            <div className="border-b border-border bg-card px-3 py-3 sm:px-5 flex items-start justify-between gap-2 shrink-0">
              <div className="space-y-2 min-w-0">
                {/* Meta pills row */}
                <div className="flex flex-wrap items-center gap-2 text-[11px] font-mono text-zinc-400">
                  <span className="text-zinc-200 font-bold">Wazuh ID: {detail.alert.wazuh_alert_id}</span>
                  <span className="text-zinc-700">•</span>
                  <div className="flex items-center gap-1 text-zinc-400">
                    <Clock className="size-3" />
                    <span>{new Date(detail.alert.ingested_at).toUTCString()}</span>
                  </div>
                  <span className="text-zinc-700">•</span>
                  <span className="px-1.5 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-300 font-semibold">
                    Level {detail.alert.rule_level}
                  </span>
                  <span className="text-zinc-700">•</span>
                  <span className="text-cyan-400 font-semibold">Rule {detail.alert.rule_id}</span>
                </div>

                {/* Threat description */}
                <h2 className="text-base font-bold text-zinc-50 font-sans leading-snug">
                  {detail.alert.rule_description}
                </h2>

                {/* Sub details: MITRE, Host, Process */}
                <div className="flex flex-wrap items-center gap-3 text-xs font-mono text-zinc-400">
                  {/* MITRE Tags */}
                  <div className="flex items-center gap-1.5">
                    <Shield className="size-3 text-zinc-500" />
                    <span className="text-zinc-300">{detail.alert.mitre_tactics.join(', ')}</span>
                    <span className="text-zinc-600">({detail.alert.mitre_techniques.join(', ')})</span>
                  </div>

                  <span className="text-zinc-700 hidden sm:inline">•</span>

                  {/* Host Context */}
                  <div className="flex items-center gap-2">
                    <span className="text-zinc-200 font-semibold">{detail.alert.agent_name}</span>
                    <span className="px-1.5 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400 text-[10px] font-mono">
                      #{detail.alert.agent_id}
                    </span>
                    <span className="text-zinc-500">({detail.alert.src_ip || 'Internal'})</span>
                    {assetTier && <AssetTierBadge tier={assetTier} />}
                  </div>

                  {detail.alert.process_signature && (
                    <>
                      <span className="text-zinc-700 hidden md:inline">•</span>
                      <div className="hidden md:flex items-center gap-1.5 text-zinc-400">
                        <Terminal className="size-3 text-zinc-500" />
                        <span className="truncate max-w-xs">{detail.alert.process_signature}</span>
                      </div>
                    </>
                  )}
                </div>
              </div>

              {/* Close Button */}
              <Button type="button" onClick={close} size="icon" variant="ghost" className="size-11"
                title="Close alert (Esc)" aria-label="Close alert">
                <X className="size-5" />
              </Button>
            </div>

            <div className={`flex flex-wrap items-center gap-1 border-b border-border px-2 py-1 ${auditTrail?.length ? 'lg:justify-end' : 'lg:hidden'}`} role="group" aria-label="Review sections">
              <Button type="button" size="sm" variant={mobilePane === 'assessment' ? 'secondary' : 'ghost'}
                className="min-h-9 lg:hidden" aria-pressed={mobilePane === 'assessment'} onClick={() => setMobilePane('assessment')}>Assessment</Button>
              <Button type="button" size="sm" variant={mobilePane === 'evidence' ? 'secondary' : 'ghost'}
                className="min-h-9 lg:hidden" aria-pressed={mobilePane === 'evidence'} onClick={() => setMobilePane('evidence')}>Evidence</Button>
              {!!auditTrail?.length && (
                <Button type="button" size="sm" variant="ghost" className="min-h-9" onClick={() => {
                  setMobilePane('assessment');
                  requestAnimationFrame(() => document.getElementById('alert-decision-history')?.focus());
                }}>Decision history</Button>
              )}
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto lg:grid lg:grid-cols-2 lg:divide-x lg:divide-border lg:overflow-hidden">
              <div className={mobilePane === 'assessment' ? 'min-h-0 min-w-0' : 'hidden min-h-0 min-w-0 lg:block'}>
              <AssessmentPane
                alertDetail={detail}
                selectedCitationKey={citation?.key ?? null}
                onSelectCitationKey={(key) => {
                  setMobilePane('evidence');
                  setCitation({ key });
                }}
                savedAuditId={savedAuditId}
              />
              </div>

              <div className={mobilePane === 'evidence' ? 'min-h-0 min-w-0' : 'hidden min-h-0 min-w-0 lg:block'}>
              {detail.evidence_pack ? (
                <EvidenceTreePane
                  evidencePack={detail.evidence_pack}
                  citedEvidenceKeys={(detail.assessment || detail.ai_assessment)?.cited_evidence_keys || []}
                  citation={citation}
                />
              ) : (
                <div className="flex-1 grid place-items-center p-6 text-sm text-zinc-400">
                  {detail.alert.status === 'PENDING_REVIEW' ? 'Evidence pack pending.' : 'Evidence pack unavailable.'}
                </div>
              )}
              </div>
            </div>

            {/* Inline Submission Error Banner */}
            {submitError && (
              <div role="alert" className="mx-5 mb-2 p-3 rounded-lg bg-red-950/70 border border-red-800 text-red-200 text-xs font-mono flex flex-wrap items-center justify-between gap-2 shrink-0">
                <div className="flex items-center gap-2">
                  <AlertCircle className="size-4 text-red-400 shrink-0" />
                  <span>{submitError}</span>
                </div>
                <button type="button" onClick={refreshDetail} className="rounded border border-red-700 px-3 py-1">Refresh alert</button>
              </div>
            )}

            {/* Sticky Action Footer */}
            <DecisionActionPanel
              alert={detail.alert}
              assessment={detail.assessment || detail.ai_assessment}
              availableActions={detail.available_actions}
              isSubmitting={isSubmitting}
              onSubmitDecision={handleSubmitDecision}
              onCloseModal={close}
            />
          </>
        )}
      </DialogContent>
    </Dialog>
  );
};
