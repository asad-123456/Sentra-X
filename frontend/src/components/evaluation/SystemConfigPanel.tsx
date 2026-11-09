import React, { useState } from 'react';
import {
  Server,
  Radio,
  Sliders,
  CheckCircle2,
  Save,
  RotateCcw,
  AlertCircle,
} from 'lucide-react';
import type { SystemConfig, LLMProvider } from '../../types/sentrax';

interface SystemConfigPanelProps {
  config: SystemConfig;
  onSave: (updated: Partial<SystemConfig>) => Promise<void>;
}

export const SystemConfigPanel: React.FC<SystemConfigPanelProps> = ({ config, onSave }) => {
  const [wazuhEndpoint, setWazuhEndpoint] = useState(config.wazuh_endpoint);
  const [pollingInterval, setPollingInterval] = useState(config.polling_interval_seconds);
  const [minRuleLevel, setMinRuleLevel] = useState(config.min_rule_level);
  const [llmProvider, setLlmProvider] = useState<LLMProvider>(config.llm_provider);
  const [modelName, setModelName] = useState(config.model_name);
  const [abstentionThreshold, setAbstentionThreshold] = useState(config.abstention_threshold);
  const [maxExemplars, setMaxExemplars] = useState(config.max_exemplars_injected);

  const [saving, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleProviderChange = (provider: LLMProvider) => {
    setLlmProvider(provider);
    if (provider === 'Gemini') {
      setModelName('gemini-2.5-flash');
    } else {
      setModelName('claude-3-5-sonnet');
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setErrorMsg(null);
    try {
      await onSave({
        wazuh_endpoint: wazuhEndpoint,
        polling_interval_seconds: Number(pollingInterval),
        min_rule_level: Number(minRuleLevel),
        llm_provider: llmProvider,
        model_name: modelName,
        abstention_threshold: Number(abstentionThreshold),
        max_exemplars_injected: Number(maxExemplars),
      });
      setSuccessMsg(true);
      setTimeout(() => setSuccessMsg(false), 2500);
    } catch (err) {
      console.error('Failed to save config:', err);
      setErrorMsg(err instanceof Error ? err.message : 'Failed to update system configuration.');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setWazuhEndpoint(config.wazuh_endpoint);
    setPollingInterval(config.polling_interval_seconds);
    setMinRuleLevel(config.min_rule_level);
    setLlmProvider(config.llm_provider);
    setModelName(config.model_name);
    setAbstentionThreshold(config.abstention_threshold);
    setMaxExemplars(config.max_exemplars_injected);
    setErrorMsg(null);
  };

  return (
    <div className="bg-zinc-950 border border-zinc-800 rounded-xl overflow-hidden">
      <div className="p-4 border-b border-zinc-800/80 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold font-mono text-zinc-100 flex items-center gap-2">
            <Sliders className="size-4 text-zinc-400" />
            SIEM Ingestion & Inference Parameters
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Configure SIEM ingestion polling rate, noise filter threshold, and active inference model
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 text-xs font-mono px-2.5 py-1 rounded-full bg-emerald-950/60 border border-emerald-800/60 text-emerald-400">
            <span className="size-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Wazuh Master Connected
          </span>
        </div>
      </div>

      <form onSubmit={handleSave} className="p-6 space-y-6">
        {errorMsg && (
          <div className="flex items-center justify-between p-3 rounded-lg bg-red-950/40 border border-red-800/60 text-xs text-red-200 font-mono">
            <div className="flex items-center gap-2">
              <AlertCircle className="size-4 text-red-400 shrink-0" />
              <span>{errorMsg}</span>
            </div>
            <button
              type="button"
              onClick={() => setErrorMsg(null)}
              className="text-red-400 hover:text-red-200 text-xs ml-4"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Section 1: SIEM Ingestion Parameters */}
        <div className="space-y-4">
          <div className="text-xs font-mono uppercase text-zinc-500 font-semibold tracking-wider flex items-center gap-2">
            <Server className="size-3.5" />
            1. Wazuh SIEM Poller Configuration
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="md:col-span-2 space-y-1.5">
              <label className="text-xs font-mono text-zinc-400">
                Wazuh API Master Endpoint
              </label>
              <input
                type="text"
                value={wazuhEndpoint}
                onChange={(e) => setWazuhEndpoint(e.target.value)}
                className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded-lg text-xs font-mono text-zinc-100 focus:outline-none focus:border-zinc-600"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-mono text-zinc-400">
                Polling Interval (Seconds)
              </label>
              <input
                type="number"
                min={5}
                max={300}
                value={pollingInterval}
                onChange={(e) => setPollingInterval(Number(e.target.value))}
                className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded-lg text-xs font-mono text-zinc-100 focus:outline-none focus:border-zinc-600"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs font-mono text-zinc-400 flex items-center justify-between">
                <span>Minimum Alert Rule Level Threshold</span>
                <span className="text-zinc-500 text-[11px]">Default: 4</span>
              </label>
              <input
                type="number"
                min={1}
                max={15}
                value={minRuleLevel}
                onChange={(e) => setMinRuleLevel(Number(e.target.value))}
                className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded-lg text-xs font-mono text-zinc-100 focus:outline-none focus:border-zinc-600"
              />
              <p className="text-[11px] text-zinc-500">
                Alerts below this rule level are treated as background noise and discarded before triage.
              </p>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-mono text-zinc-400 flex items-center justify-between">
                <span>Max Injected Few-Shot Exemplars</span>
                <span className="text-zinc-500 text-[11px]">Default: 2</span>
              </label>
              <input
                type="number"
                min={0}
                max={5}
                value={maxExemplars}
                onChange={(e) => setMaxExemplars(Number(e.target.value))}
                className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded-lg text-xs font-mono text-zinc-100 focus:outline-none focus:border-zinc-600"
              />
              <p className="text-[11px] text-zinc-500">
                Maximum verified historical supervisor feedback examples injected into the prompt context.
              </p>
            </div>
          </div>
        </div>

        {/* Section 2: LLM Provider & Uncertainty Thresholds */}
        <div className="space-y-4 pt-4 border-t border-zinc-800/80">
          <div className="text-xs font-mono uppercase text-zinc-500 font-semibold tracking-wider flex items-center gap-2">
            <Radio className="size-3.5" />
            2. Inference Engine & Guardrail Thresholds
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-mono text-zinc-400">
                Active LLM Provider
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => handleProviderChange('Gemini')}
                  className={`p-3 rounded-lg border text-xs font-mono text-left transition-all ${
                    llmProvider === 'Gemini'
                      ? 'bg-zinc-900 border-zinc-400 text-zinc-100'
                      : 'bg-zinc-950 border-zinc-800 text-zinc-400 hover:border-zinc-700'
                  }`}
                >
                  <div className="font-semibold text-zinc-200">Google Gemini</div>
                  <div className="text-[11px] text-zinc-500 mt-0.5">gemini-2.5-flash</div>
                </button>

                <button
                  type="button"
                  onClick={() => handleProviderChange('Claude')}
                  className={`p-3 rounded-lg border text-xs font-mono text-left transition-all ${
                    llmProvider === 'Claude'
                      ? 'bg-zinc-900 border-zinc-400 text-zinc-100'
                      : 'bg-zinc-950 border-zinc-800 text-zinc-400 hover:border-zinc-700'
                  }`}
                >
                  <div className="font-semibold text-zinc-200">Anthropic Claude</div>
                  <div className="text-[11px] text-zinc-500 mt-0.5">claude-3-5-sonnet</div>
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-mono text-zinc-400 flex items-center justify-between">
                <span>Abstention Confidence Threshold</span>
                <span className="text-emerald-400 font-semibold">{abstentionThreshold.toFixed(2)}</span>
              </label>
              <div className="space-y-1">
                <input
                  type="range"
                  min="0.40"
                  max="0.95"
                  step="0.05"
                  value={abstentionThreshold}
                  onChange={(e) => setAbstentionThreshold(Number(e.target.value))}
                  className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-zinc-100"
                />
                <div className="flex justify-between text-[10px] font-mono text-zinc-500">
                  <span>0.40 (Permissive)</span>
                  <span>0.60 (Recommended)</span>
                  <span>0.95 (Strict)</span>
                </div>
              </div>
              <p className="text-[11px] text-zinc-500">
                Any AI assessment with confidence score below this value is automatically routed to analyst review.
              </p>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="pt-4 border-t border-zinc-800/80 flex items-center justify-between">
          <div className="flex items-center gap-2">
            {successMsg && (
              <span className="inline-flex items-center gap-1 text-xs font-mono text-emerald-400 animate-in fade-in">
                <CheckCircle2 className="size-3.5" />
                Parameters updated successfully
              </span>
            )}
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleReset}
              className="px-3 py-1.5 rounded-lg border border-zinc-800 text-xs font-mono text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 transition-colors flex items-center gap-1.5"
            >
              <RotateCcw className="size-3" />
              Reset
            </button>

            <button
              type="submit"
              disabled={saving}
              className="px-4 py-1.5 rounded-lg bg-zinc-100 text-zinc-950 font-mono text-xs font-semibold hover:bg-zinc-200 transition-colors flex items-center gap-1.5 disabled:opacity-50"
            >
              <Save className="size-3.5" />
              {saving ? 'Saving...' : 'Save Configuration'}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
};

