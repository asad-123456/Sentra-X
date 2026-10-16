import React, { useState, useEffect } from 'react';
import type { FeedbackExemplar, Asset, AssetCriticalityTier } from '../types/sentrax';
import {
  getExemplars,
  toggleExemplarActive,
  getAssets,
  updateAssetCriticality,
  registerAsset,
} from '../api/services';
import { ExemplarTable } from '../components/governance/ExemplarTable';
import { AssetRegistryTable } from '../components/governance/AssetRegistryTable';
import {
  Server,
  RotateCcw,
  Sparkles,
  AlertCircle,
} from 'lucide-react';

type GovernanceTab = 'exemplars' | 'assets';

export const GovernanceView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<GovernanceTab>('exemplars');

  // Exemplars State
  const [exemplars, setExemplars] = useState<FeedbackExemplar[]>([]);
  const [loadingExemplars, setLoadingExemplars] = useState(true);

  // Assets State
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loadingAssets, setLoadingAssets] = useState(true);

  const [error, setError] = useState<string | null>(null);

  // Load data function for manual retry / refresh
  const reloadData = () => {
    setLoadingExemplars(true);
    setLoadingAssets(true);
    setError(null);
    getExemplars()
      .then((data) => {
        setExemplars(data);
        setLoadingExemplars(false);
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : 'Failed to fetch exemplars.';
        setError(msg);
        setLoadingExemplars(false);
      });

    getAssets()
      .then((data) => {
        setAssets(data);
        setLoadingAssets(false);
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : 'Failed to fetch monitored assets.';
        setError(msg);
        setLoadingAssets(false);
      });
  };

  useEffect(() => {
    let isCancelled = false;
    getExemplars()
      .then((data) => {
        if (!isCancelled) {
          setExemplars(data);
          setLoadingExemplars(false);
        }
      })
      .catch((err: unknown) => {
        if (!isCancelled) {
          const msg = err instanceof Error ? err.message : 'Failed to fetch exemplars.';
          setError(msg);
          setLoadingExemplars(false);
        }
      });

    getAssets()
      .then((data) => {
        if (!isCancelled) {
          setAssets(data);
          setLoadingAssets(false);
        }
      })
      .catch((err: unknown) => {
        if (!isCancelled) {
          const msg = err instanceof Error ? err.message : 'Failed to fetch monitored assets.';
          setError(msg);
          setLoadingAssets(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, []);


  const handleToggleExemplarActive = async (id: string, active: boolean) => {
    try {
      const updated = await toggleExemplarActive(id, active);
      setExemplars((prev) =>
        prev.map((e) => (e.id === updated.id ? { ...e, is_active: updated.is_active } : e))
      );
    } catch (err) {
      console.error('Failed to toggle exemplar active state:', err);
      alert('Failed to update exemplar status.');
    }
  };

  const handleUpdateCriticality = async (
    agentId: string,
    tier: AssetCriticalityTier,
    description?: string
  ) => {
    try {
      const updated = await updateAssetCriticality(agentId, tier, description);
      setAssets((prev) =>
        prev.map((a) => (a.agent_id === updated.agent_id ? updated : a))
      );
    } catch (err) {
      console.error('Failed to update asset criticality:', err);
      throw err;
    }
  };

  const handleRegisterAsset = async (
    newAsset: Omit<Asset, 'id' | 'created_at' | 'updated_at'>
  ) => {
    try {
      const created = await registerAsset(newAsset);
      setAssets((prev) => [created, ...prev]);
    } catch (err) {
      console.error('Failed to register asset:', err);
      throw err;
    }
  };

  const handleRefresh = () => {
    reloadData();
  };


  const activeExemplarCount = exemplars.filter((e) => e.is_active).length;

  return (
    <div className="space-y-6">
      {/* View Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-xl font-bold tracking-tight text-zinc-50 font-mono">
            Governance &amp; Host Registry
          </h1>
          <p className="text-xs text-zinc-400 font-sans">
            Manage few-shot calibration exemplars and host criticality tiers.
          </p>
        </div>

        {/* Refresh Action */}
        <button
          type="button"
          onClick={handleRefresh}
          className="p-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer self-start md:self-auto"
          title="Refresh governance registry"
        >
          <RotateCcw className={`size-4 ${loadingExemplars || loadingAssets ? 'animate-spin text-cyan-400' : ''}`} />
        </button>
      </div>

      {/* Primary Tab Navigation */}
      <div className="border-b border-zinc-850 flex items-center gap-2">
        <button
          type="button"
          onClick={() => setActiveTab('exemplars')}
          className={`flex items-center gap-2 px-4 py-2.5 border-b-2 font-mono text-xs font-semibold transition-colors cursor-pointer ${
            activeTab === 'exemplars'
              ? 'border-cyan-400 text-zinc-100 bg-zinc-900/40'
              : 'border-transparent text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/20'
          }`}
        >
          <Sparkles className="size-3.5 text-cyan-400" />
          <span>Few-Shot Exemplars</span>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-zinc-900 border border-zinc-800 text-zinc-300">
            {activeExemplarCount} active / {exemplars.length} total
          </span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('assets')}
          className={`flex items-center gap-2 px-4 py-2.5 border-b-2 font-mono text-xs font-semibold transition-colors cursor-pointer ${
            activeTab === 'assets'
              ? 'border-cyan-400 text-zinc-100 bg-zinc-900/40'
              : 'border-transparent text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/20'
          }`}
        >
          <Server className="size-3.5 text-zinc-400" />
          <span>Host Criticality</span>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-zinc-900 border border-zinc-800 text-zinc-300">
            {assets.length} hosts
          </span>
        </button>
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

      {/* Tab 1: Exemplars Table */}
      {activeTab === 'exemplars' && (
        <div className="space-y-4">
          <ExemplarTable
            exemplars={exemplars}
            isLoading={loadingExemplars}
            onToggleActive={handleToggleExemplarActive}
          />
        </div>
      )}

      {/* Tab 2: Asset Criticality Registry */}
      {activeTab === 'assets' && (
        <div className="space-y-4">
          <AssetRegistryTable
            assets={assets}
            isLoading={loadingAssets}
            onUpdateCriticality={handleUpdateCriticality}
            onRegisterAsset={handleRegisterAsset}
          />
        </div>
      )}
    </div>
  );
};
