import React, { useState } from 'react';
import type { Asset, AssetCriticalityTier } from '../../types/sentrax';
import { AssetTierBadge } from '../badges/AssetTierBadge';
import {
  Search,
  Plus,
  Shield,
  Save,
  Check,
  X,
  Loader2,
  Server,
  AlertCircle,
} from 'lucide-react';

interface AssetRegistryTableProps {
  assets: Asset[];
  isLoading: boolean;
  onUpdateCriticality: (
    agentId: string,
    tier: AssetCriticalityTier,
    description?: string
  ) => Promise<void>;
  onRegisterAsset: (
    newAsset: Omit<Asset, 'id' | 'created_at' | 'updated_at'>
  ) => Promise<void>;
}

export const AssetRegistryTable: React.FC<AssetRegistryTableProps> = ({
  assets,
  isLoading,
  onUpdateCriticality,
  onRegisterAsset,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTier, setEditTier] = useState<AssetCriticalityTier>('MEDIUM');
  const [editDesc, setEditDesc] = useState<string>('');
  const [isSaving, setIsSaving] = useState(false);
  const [savedSuccessId, setSavedSuccessId] = useState<string | null>(null);

  // New Asset Form Modal State
  const [showAddForm, setShowAddForm] = useState(false);
  const [newAgentId, setNewAgentId] = useState('');
  const [newHostname, setNewHostname] = useState('');
  const [newIpAddress, setNewIpAddress] = useState('');
  const [newTier, setNewTier] = useState<AssetCriticalityTier>('MEDIUM');
  const [newDesc, setNewDesc] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [isRegistering, setIsRegistering] = useState(false);

  const filteredAssets = assets.filter((asset) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      asset.agent_id.toLowerCase().includes(q) ||
      asset.hostname.toLowerCase().includes(q) ||
      asset.ip_address.toLowerCase().includes(q) ||
      (asset.description && asset.description.toLowerCase().includes(q))
    );
  });

  const handleStartEdit = (asset: Asset) => {
    setEditingId(asset.agent_id);
    setEditTier(asset.criticality_tier);
    setEditDesc(asset.description || '');
  };

  const handleCancelEdit = () => {
    setEditingId(null);
  };

  const handleSaveEdit = async (agentId: string) => {
    setIsSaving(true);
    try {
      await onUpdateCriticality(agentId, editTier, editDesc);
      setEditingId(null);
      setSavedSuccessId(agentId);
      setTimeout(() => setSavedSuccessId(null), 2500);
    } catch (err) {
      console.error('Failed to update asset criticality:', err);
      alert('Failed to update asset.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newAgentId.trim() || !newHostname.trim() || !newIpAddress.trim()) {
      setFormError('Agent ID, Hostname, and IP Address are mandatory fields.');
      return;
    }
    setFormError(null);
    setIsRegistering(true);
    try {
      await onRegisterAsset({
        agent_id: newAgentId.trim(),
        hostname: newHostname.trim().toUpperCase(),
        ip_address: newIpAddress.trim(),
        criticality_tier: newTier,
        description: newDesc.trim() || undefined,
      });
      // Reset form
      setNewAgentId('');
      setNewHostname('');
      setNewIpAddress('');
      setNewTier('MEDIUM');
      setNewDesc('');
      setShowAddForm(false);
    } catch (err) {
      console.error('Failed to register asset:', err);
      setFormError(err instanceof Error ? err.message : 'Asset registration failed.');
    } finally {
      setIsRegistering(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Control Bar: Search & Register Asset Button */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3.5 rounded-xl bg-zinc-950 border border-zinc-850">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-zinc-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by agent ID, hostname, IP, or description..."
            className="w-full pl-9 pr-3 py-1.5 bg-zinc-900 border border-zinc-800 rounded-lg text-xs font-mono text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-700 transition-colors"
          />
        </div>

        <button
          type="button"
          onClick={() => setShowAddForm(!showAddForm)}
          className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-white hover:bg-zinc-200 text-black font-semibold text-xs font-mono shadow-md transition-colors cursor-pointer self-start sm:self-auto"
        >
          <Plus className="size-3.5" />
          <span>Register Host</span>
        </button>
      </div>

      {/* New Asset Registration Drawer/Modal */}
      {showAddForm && (
        <form
          onSubmit={handleCreateSubmit}
          className="p-4 rounded-xl bg-zinc-900/90 border border-zinc-750 space-y-4 animate-in fade-in"
        >
          <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
            <div className="flex items-center gap-2 text-xs font-mono font-bold text-zinc-100">
              <Server className="size-4 text-cyan-400" />
              <span>Register Monitored Host into Asset Registry</span>
            </div>
            <button
              type="button"
              onClick={() => setShowAddForm(false)}
              className="text-zinc-400 hover:text-zinc-200"
            >
              <X className="size-4" />
            </button>
          </div>

          {formError && (
            <div className="p-3 rounded-lg bg-red-950/60 border border-red-800 text-red-200 text-xs font-mono flex items-center gap-2">
              <AlertCircle className="size-4 text-red-400 shrink-0" />
              <span>{formError}</span>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
            <div className="space-y-1">
              <label className="text-[10px] font-mono text-zinc-400">AGENT ID *</label>
              <input
                type="text"
                value={newAgentId}
                onChange={(e) => setNewAgentId(e.target.value)}
                placeholder="007"
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs font-mono text-zinc-100 focus:outline-none focus:border-zinc-700"
                required
              />
            </div>

            <div className="space-y-1">
              <label className="text-[10px] font-mono text-zinc-400">HOSTNAME *</label>
              <input
                type="text"
                value={newHostname}
                onChange={(e) => setNewHostname(e.target.value)}
                placeholder="CORP-EXCHANGE-01"
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs font-mono text-zinc-100 focus:outline-none focus:border-zinc-700 uppercase"
                required
              />
            </div>

            <div className="space-y-1">
              <label className="text-[10px] font-mono text-zinc-400">IP ADDRESS *</label>
              <input
                type="text"
                value={newIpAddress}
                onChange={(e) => setNewIpAddress(e.target.value)}
                placeholder="10.0.1.25"
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs font-mono text-zinc-100 focus:outline-none focus:border-zinc-700"
                required
              />
            </div>

            <div className="space-y-1">
              <label className="text-[10px] font-mono text-zinc-400">CRITICALITY TIER</label>
              <select
                value={newTier}
                onChange={(e) => setNewTier(e.target.value as AssetCriticalityTier)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs font-mono text-zinc-100 focus:outline-none focus:border-zinc-700 cursor-pointer"
              >
                <option value="CRITICAL">CRITICAL (Crown Jewel)</option>
                <option value="HIGH">HIGH (Infrastructure)</option>
                <option value="MEDIUM">MEDIUM (Endpoint)</option>
                <option value="LOW">LOW (Isolated DMZ)</option>
              </select>
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-[10px] font-mono text-zinc-400">DESCRIPTION (OPTIONAL)</label>
            <input
              type="text"
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              placeholder="Primary internal email server and mail routing gateway..."
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs font-sans text-zinc-100 focus:outline-none focus:border-zinc-700"
            />
          </div>

          <div className="flex items-center justify-end gap-2.5 pt-1">
            <button
              type="button"
              onClick={() => setShowAddForm(false)}
              className="px-3 py-1.5 rounded-lg bg-zinc-950 hover:bg-zinc-800 border border-zinc-800 text-xs font-mono text-zinc-400 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isRegistering}
              className="px-4 py-1.5 rounded-lg bg-white hover:bg-zinc-200 text-black font-semibold text-xs font-mono shadow-md transition-colors cursor-pointer disabled:opacity-50"
            >
              {isRegistering ? 'Registering...' : 'Register Asset'}
            </button>
          </div>
        </form>
      )}

      {/* Asset Table */}
      <div className="rounded-xl border border-zinc-850 bg-zinc-950 overflow-hidden shadow-sm">
        <div className="overflow-x-auto custom-scrollbar">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-zinc-850 bg-zinc-900/60 font-mono text-[10px] text-zinc-400 uppercase tracking-wider">
                <th className="py-3 px-4 font-semibold">Agent ID &amp; Hostname</th>
                <th className="py-3 px-4 font-semibold">IP Address</th>
                <th className="py-3 px-4 font-semibold">Criticality Tier</th>
                <th className="py-3 px-4 font-semibold max-w-sm">Asset Description</th>
                <th className="py-3 px-4 font-semibold">Updated</th>
                <th className="py-3 px-4 font-semibold text-right">Registry Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-850/60">
              {isLoading && (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-zinc-500 font-mono">
                    <Loader2 className="size-5 text-cyan-400 animate-spin mx-auto mb-2" />
                    <span>Loading monitored assets from registry...</span>
                  </td>
                </tr>
              )}

              {!isLoading && filteredAssets.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-zinc-500 font-mono space-y-1">
                    <Shield className="size-6 text-zinc-600 mx-auto" />
                    <div className="text-zinc-300 font-bold">No assets found</div>
                    <div className="text-[11px] text-zinc-500 font-sans">
                      Try searching with a different hostname or IP address.
                    </div>
                  </td>
                </tr>
              )}

              {!isLoading &&
                filteredAssets.map((asset) => {
                  const isEditing = editingId === asset.agent_id;
                  const isSavedSuccess = savedSuccessId === asset.agent_id;

                  return (
                    <tr key={asset.agent_id} className="hover:bg-zinc-900/40 transition-colors">
                      {/* Agent ID & Hostname */}
                      <td className="py-3.5 px-4 font-mono">
                        <div className="font-bold text-zinc-100 flex items-center gap-1.5">
                          <span>{asset.hostname}</span>
                        </div>
                        <div className="text-[10px] text-zinc-500 font-mono pt-0.5">
                          Agent ID: {asset.agent_id}
                        </div>
                      </td>

                      {/* IP Address */}
                      <td className="py-3.5 px-4 font-mono text-zinc-300">
                        {asset.ip_address}
                      </td>

                      {/* Criticality Tier */}
                      <td className="py-3.5 px-4">
                        {isEditing ? (
                          <select
                            value={editTier}
                            onChange={(e) => setEditTier(e.target.value as AssetCriticalityTier)}
                            className="bg-zinc-900 border border-zinc-700 rounded-lg px-2.5 py-1 text-xs font-mono text-zinc-100 focus:outline-none focus:border-cyan-500 cursor-pointer"
                          >
                            <option value="CRITICAL">CRITICAL (Crown Jewel)</option>
                            <option value="HIGH">HIGH (Infrastructure)</option>
                            <option value="MEDIUM">MEDIUM (Endpoint)</option>
                            <option value="LOW">LOW (Isolated DMZ)</option>
                          </select>
                        ) : (
                          <div className="flex items-center gap-2">
                            <AssetTierBadge tier={asset.criticality_tier} />
                            {isSavedSuccess && (
                              <span className="inline-flex items-center gap-1 text-[10px] font-mono text-emerald-400">
                                <Check className="size-3" />
                                <span>Saved</span>
                              </span>
                            )}
                          </div>
                        )}
                      </td>

                      {/* Description */}
                      <td className="py-3.5 px-4 max-w-sm">
                        {isEditing ? (
                          <input
                            type="text"
                            value={editDesc}
                            onChange={(e) => setEditDesc(e.target.value)}
                            placeholder="Asset purpose or business function..."
                            className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-2.5 py-1 text-xs font-sans text-zinc-100 focus:outline-none focus:border-cyan-500"
                          />
                        ) : (
                          <div className="text-zinc-300 font-sans text-xs">
                            {asset.description || <span className="text-zinc-600 italic">No description provided</span>}
                          </div>
                        )}
                      </td>

                      {/* Updated Date */}
                      <td className="py-3.5 px-4 font-mono text-[11px] text-zinc-400">
                        {new Date(asset.updated_at).toLocaleDateString()}
                      </td>

                      {/* Action */}
                      <td className="py-3.5 px-4 text-right">
                        {isEditing ? (
                          <div className="inline-flex items-center gap-2">
                            <button
                              type="button"
                              onClick={handleCancelEdit}
                              disabled={isSaving}
                              className="px-2.5 py-1 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-xs font-mono text-zinc-400 transition-colors cursor-pointer"
                            >
                              Cancel
                            </button>
                            <button
                              type="button"
                              onClick={() => handleSaveEdit(asset.agent_id)}
                              disabled={isSaving}
                              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-white hover:bg-zinc-200 text-black text-xs font-mono font-bold shadow-md transition-colors cursor-pointer disabled:opacity-50"
                            >
                              {isSaving ? <Loader2 className="size-3 animate-spin" /> : <Save className="size-3" />}
                              <span>Save</span>
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => handleStartEdit(asset)}
                            className="px-3 py-1 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-xs font-mono text-zinc-300 hover:text-white transition-colors cursor-pointer"
                          >
                            Configure
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

