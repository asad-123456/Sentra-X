import { RotateCcw } from 'lucide-react';
import type { RuntimeSettings, RuntimeSettingsState } from '../../types/sentrax';

const INGESTION_LABELS: Record<RuntimeSettings['ingestion_mode'], string> = {
  poll: 'Indexer polling',
  webhook: 'Signed webhook',
  replay: 'Replay',
  unknown: 'Unknown',
};

const WORKER_LABELS: Record<RuntimeSettings['worker_status'], string> = {
  running: 'Running',
  disabled: 'Disabled',
  stopped: 'Stopped',
};

interface RuntimeSettingsPanelProps {
  runtime: RuntimeSettingsState;
  onRefresh: () => void;
}

export function RuntimeSettingsPanel({ runtime, onRefresh }: RuntimeSettingsPanelProps) {
  const config = runtime.status === 'ready' ? runtime.settings : null;
  const loading = runtime.status === 'loading';
  const label = 'text-xs text-zinc-400';
  const value = 'break-words text-sm font-medium text-zinc-100';

  return (
    <section aria-labelledby="runtime-settings-heading" className="surface">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-zinc-800 px-4 py-4 sm:px-6">
        <div>
          <h2 id="runtime-settings-heading" className="text-sm font-semibold text-zinc-100">Runtime settings</h2>
          <p className="mt-1 text-xs text-zinc-400">
            After editing the backend environment, recreate the Compose backend or restart the local process.
          </p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-200 hover:bg-zinc-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-400 disabled:opacity-50"
        >
          <RotateCcw className="size-3.5" aria-hidden="true" />
          Refresh settings
        </button>
      </div>
      {config ? (
        <div className="grid gap-6 px-4 py-5 sm:px-6 xl:grid-cols-2">
          <div>
            <h3 className="mb-3 text-sm font-semibold text-zinc-200">Wazuh ingestion</h3>
            <dl className="grid grid-cols-2 gap-x-3 gap-y-1.5">
              <dt className={label}>Ingestion mode</dt>
              <dd className={value}>{INGESTION_LABELS[config.ingestion_mode]}</dd>
              <dt className={label}>Minimum rule level</dt>
              <dd className={value}>{config.min_rule_level}</dd>
              {config.polling_interval_seconds !== null && (
                <>
                  <dt className={label}>Polling interval</dt>
                  <dd className={value}>{config.polling_interval_seconds} seconds</dd>
                </>
              )}
            </dl>
          </div>
          <div>
            <h3 className="mb-3 text-sm font-semibold text-zinc-200">AI triage worker configuration</h3>
            <dl className="grid grid-cols-2 gap-x-3 gap-y-1.5">
              <dt className={label}>Worker process</dt>
              <dd className={value}>{WORKER_LABELS[config.worker_status]}</dd>
              <dt className={label}>Active workers</dt>
              <dd className={value}>{config.active_workers}</dd>
              <dt className={label}>Inference provider</dt>
              <dd className={value}>{config.llm_provider ?? 'None active'}</dd>
              <dt className={label}>Model</dt>
              <dd className={value}>{config.model_name ?? 'None active'}</dd>
              <dt className={label}>Abstention threshold</dt>
              <dd className={value}>{config.abstention_threshold.toFixed(2)}</dd>
              <dt className={label}>Maximum feedback examples</dt>
              <dd className={value}>{config.max_exemplars_injected}</dd>
            </dl>
            <p className="mt-3 text-xs text-zinc-400">Provider connectivity is unchecked here.</p>
          </div>
        </div>
      ) : (
        <p role="status" className="px-4 py-5 text-sm text-zinc-300 sm:px-6">
          {loading ? 'Loading runtime settings…' : 'Runtime settings are unavailable. Select Refresh settings to try again.'}
        </p>
      )}
      {runtime.status === 'ready' && (
        <p role="status" className="border-t border-border px-4 py-3 text-xs text-muted-foreground sm:px-6">
          Last checked <time dateTime={runtime.checkedAt}>{new Date(runtime.checkedAt).toLocaleTimeString()}</time>
        </p>
      )}
    </section>
  );
}
