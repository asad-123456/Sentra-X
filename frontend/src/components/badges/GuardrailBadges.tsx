import React from 'react';
import { Shield, AlertCircle, ShieldAlert, Sparkles } from 'lucide-react';

interface GuardrailBadgesProps {
  safetyFloorTriggered?: boolean;
  abstentionTriggered?: boolean;
  injectionSuspect?: boolean;
  hasFewShot?: boolean;
  className?: string;
}

export const GuardrailBadges: React.FC<GuardrailBadgesProps> = ({
  safetyFloorTriggered = false,
  abstentionTriggered = false,
  injectionSuspect = false,
  hasFewShot = false,
  className = '',
}) => {
  const hasAnyGuardrail =
    safetyFloorTriggered || abstentionTriggered || injectionSuspect || hasFewShot;

  if (!hasAnyGuardrail) {
    return (
      <div className={`inline-flex items-center text-zinc-600 font-mono text-xs ${className}`}>
        <span>—</span>
      </div>
    );
  }

  return (
    <div className={`inline-flex items-center gap-1.5 whitespace-nowrap shrink-0 ${className}`}>
      {safetyFloorTriggered && (
        <span
          title="Safety Floor Policy Active: Automated downgrade prohibited"
          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-medium bg-red-950/30 border border-red-500/40 text-red-300 shadow-[0_0_8px_rgba(239,68,68,0.15)] whitespace-nowrap shrink-0"
        >
          <ShieldAlert className="size-2.5 text-red-400 shrink-0" />
          <span>SAFETY FLOOR</span>
        </span>
      )}

      {abstentionTriggered && (
        <span
          title="Abstention Triggered: Routed to analyst review"
          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-medium bg-amber-950/30 border border-amber-500/40 text-amber-300 whitespace-nowrap shrink-0"
        >
          <AlertCircle className="size-2.5 text-amber-400 shrink-0" />
          <span>ABSTENTION</span>
        </span>
      )}

      {injectionSuspect && (
        <span
          title="Adversarial Prompt-Injection Detected: Untrusted delimiter sanitized"
          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-medium bg-purple-950/30 border border-purple-500/40 text-purple-300 shadow-[0_0_8px_rgba(168,85,247,0.2)] whitespace-nowrap shrink-0"
        >
          <Shield className="size-2.5 text-purple-400 shrink-0" />
          <span>INJECTION SUSPECT</span>
        </span>
      )}

      {hasFewShot && (
        <span
          title="Dynamic Few-Shot Feedback Exemplar Injected"
          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-medium bg-zinc-900 border border-zinc-700/80 text-zinc-300 whitespace-nowrap shrink-0"
        >
          <Sparkles className="size-2.5 text-zinc-400 shrink-0" />
          <span>FEW-SHOT</span>
        </span>
      )}
    </div>
  );
};

