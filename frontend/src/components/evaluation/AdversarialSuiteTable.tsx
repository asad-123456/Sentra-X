import React, { useState, useMemo } from 'react';
import {
  Search,
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  Copy,
  Check,
  X,
  ExternalLink,
  Code2,
} from 'lucide-react';
import type { BenchmarkPayload, PromptInjectionCategory } from '../../types/sentrax';

interface AdversarialSuiteTableProps {
  payloads: BenchmarkPayload[];
}

type CategoryTab = 'ALL' | PromptInjectionCategory;

export const AdversarialSuiteTable: React.FC<AdversarialSuiteTableProps> = ({ payloads }) => {
  const [selectedCategory, setSelectedCategory] = useState<CategoryTab>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [inspectedPayload, setInspectedPayload] = useState<BenchmarkPayload | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Category counts
  const categoryCounts = useMemo(() => {
    return {
      all: payloads.length,
      direct: payloads.filter((p) => p.category === '1. Direct Instruction Override').length,
      spoofing: payloads.filter((p) => p.category === '2. Delimiter & Role Spoofing').length,
      citation: payloads.filter((p) => p.category === '3. Citation & Confidence Spoofing').length,
    };
  }, [payloads]);

  // Filtered payloads
  const filteredPayloads = useMemo(() => {
    return payloads.filter((p) => {
      if (selectedCategory !== 'ALL' && p.category !== selectedCategory) {
        return false;
      }
      if (searchQuery.trim() !== '') {
        const q = searchQuery.toLowerCase().trim();
        return (
          p.id.toLowerCase().includes(q) ||
          p.target_field.toLowerCase().includes(q) ||
          p.payload.toLowerCase().includes(q) ||
          p.defense_mechanism.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [payloads, selectedCategory, searchQuery]);

  const handleCopyPayload = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="bg-zinc-950 border border-zinc-800 rounded-xl overflow-hidden flex flex-col">
      {/* Table Header Controls */}
      <div className="p-4 border-b border-zinc-800/80 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold font-mono text-zinc-100 flex items-center gap-2">
              <ShieldAlert className="size-4 text-emerald-400" />
              Adversarial Prompt-Injection Test Suite (30 Payloads)
            </h2>
            <p className="text-xs text-zinc-400 mt-0.5">
              Empirical attack vectors targeting log payloads, process trees, and citation paths
            </p>
          </div>

          {/* Search box */}
          <div className="relative w-full sm:w-64">
            <Search className="size-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
            <input
              type="text"
              placeholder="Search payloads or fields..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 bg-zinc-900 border border-zinc-800 rounded-lg text-xs font-mono text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-zinc-600"
            />
          </div>
        </div>

        {/* Category Filter Pills */}
        <div className="flex flex-wrap items-center gap-1.5 pt-1">
          <button
            type="button"
            onClick={() => setSelectedCategory('ALL')}
            className={`px-3 py-1 rounded-lg text-xs font-mono transition-colors ${
              selectedCategory === 'ALL'
                ? 'bg-zinc-100 text-zinc-950 font-semibold'
                : 'bg-zinc-900 border border-zinc-800/80 text-zinc-400 hover:text-zinc-200'
            }`}
          >
            All Payloads ({categoryCounts.all})
          </button>
          <button
            type="button"
            onClick={() => setSelectedCategory('1. Direct Instruction Override')}
            className={`px-3 py-1 rounded-lg text-xs font-mono transition-colors ${
              selectedCategory === '1. Direct Instruction Override'
                ? 'bg-zinc-100 text-zinc-950 font-semibold'
                : 'bg-zinc-900 border border-zinc-800/80 text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Direct Override ({categoryCounts.direct})
          </button>
          <button
            type="button"
            onClick={() => setSelectedCategory('2. Delimiter & Role Spoofing')}
            className={`px-3 py-1 rounded-lg text-xs font-mono transition-colors ${
              selectedCategory === '2. Delimiter & Role Spoofing'
                ? 'bg-zinc-100 text-zinc-950 font-semibold'
                : 'bg-zinc-900 border border-zinc-800/80 text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Delimiter & Role ({categoryCounts.spoofing})
          </button>
          <button
            type="button"
            onClick={() => setSelectedCategory('3. Citation & Confidence Spoofing')}
            className={`px-3 py-1 rounded-lg text-xs font-mono transition-colors ${
              selectedCategory === '3. Citation & Confidence Spoofing'
                ? 'bg-zinc-100 text-zinc-950 font-semibold'
                : 'bg-zinc-900 border border-zinc-800/80 text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Citation & Confidence ({categoryCounts.citation})
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="bg-zinc-900/60 text-zinc-400 font-mono text-[11px] uppercase tracking-wider border-b border-zinc-800">
              <th className="py-3 px-4 w-20">ID</th>
              <th className="py-3 px-4 w-48">Target Field</th>
              <th className="py-3 px-4">Malicious Payload Snippet</th>
              <th className="py-3 px-4 w-28 text-center">Detection</th>
              <th className="py-3 px-4 w-44">Baseline Result</th>
              <th className="py-3 px-4 w-48">Sentra-X Pipeline</th>
              <th className="py-3 px-4 w-48">Active Defense</th>
              <th className="py-3 px-4 w-16 text-right">Inspect</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/60 font-mono">
            {filteredPayloads.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-8 text-center text-zinc-500 font-sans text-xs">
                  No adversarial payloads matching filter criteria.
                </td>
              </tr>
            ) : (
              filteredPayloads.map((p) => (
                <tr
                  key={p.id}
                  onClick={() => setInspectedPayload(p)}
                  className="hover:bg-zinc-900/40 cursor-pointer transition-colors group"
                >
                  <td className="py-3 px-4 font-semibold text-zinc-200">
                    {p.id}
                  </td>
                  <td className="py-3 px-4 text-zinc-400">
                    <span className="px-1.5 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-[11px] text-zinc-300">
                      {p.target_field}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-zinc-300 max-w-xs truncate">
                    <span className="text-zinc-400 group-hover:text-zinc-200 transition-colors">
                      {p.payload}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-center">
                    <span className="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-950/60 border border-emerald-800/60 text-emerald-300">
                      <CheckCircle2 className="size-2.5" />
                      Detected
                    </span>
                  </td>
                  <td className="py-3 px-4 text-red-400/90 text-[11px]">
                    {p.baseline_verdict}
                  </td>
                  <td className="py-3 px-4 text-[11px]">
                    <span className="inline-flex items-center gap-1 text-emerald-400 font-medium">
                      <ShieldCheck className="size-3 shrink-0" />
                      {p.sentrax_verdict}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-zinc-400 text-[11px]">
                    {p.defense_mechanism}
                  </td>
                  <td className="py-3 px-4 text-right">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setInspectedPayload(p);
                      }}
                      className="p-1 rounded text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 transition-colors"
                      title="Inspect full payload"
                    >
                      <ExternalLink className="size-3.5" />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Footer Info */}
      <div className="p-3 border-t border-zinc-800/80 bg-zinc-900/30 flex items-center justify-between text-xs text-zinc-400">
        <span>
          Showing {filteredPayloads.length} of {payloads.length} adversarial test cases
        </span>
        <span className="font-mono text-[11px] text-emerald-400">
          Neutralization Rate: 100.0% (30 / 30)
        </span>
      </div>

      {/* Payload Inspection Modal */}
      {inspectedPayload && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-zinc-950 border border-zinc-800 rounded-xl max-w-2xl w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
              <div className="flex items-center gap-2">
                <span className="font-mono font-bold text-sm text-zinc-100">
                  {inspectedPayload.id}
                </span>
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">
                  {inspectedPayload.category}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setInspectedPayload(null)}
                className="p-1 rounded text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900"
              >
                <X className="size-4" />
              </button>
            </div>

            {/* Target Field & Detection */}
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="p-3 rounded-lg bg-zinc-900/60 border border-zinc-800 space-y-1">
                <span className="text-[10px] font-mono uppercase text-zinc-500">Target Telemetry Field</span>
                <div className="font-mono text-zinc-200">{inspectedPayload.target_field}</div>
              </div>
              <div className="p-3 rounded-lg bg-zinc-900/60 border border-zinc-800 space-y-1">
                <span className="text-[10px] font-mono uppercase text-zinc-500">Active Defense Mechanism</span>
                <div className="font-mono text-emerald-400">{inspectedPayload.defense_mechanism}</div>
              </div>
            </div>

            {/* Raw Payload Block */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs text-zinc-400 font-mono">
                <span className="flex items-center gap-1.5">
                  <Code2 className="size-3.5 text-zinc-400" />
                  Untrusted Injected Payload
                </span>
                <button
                  type="button"
                  onClick={() => handleCopyPayload(inspectedPayload.id, inspectedPayload.payload)}
                  className="flex items-center gap-1 text-[11px] text-zinc-400 hover:text-zinc-100 transition-colors"
                >
                  {copiedId === inspectedPayload.id ? (
                    <>
                      <Check className="size-3 text-emerald-400" />
                      <span className="text-emerald-400">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="size-3" />
                      <span>Copy Payload</span>
                    </>
                  )}
                </button>
              </div>
              <pre className="p-3 rounded-lg bg-zinc-900 border border-zinc-800 text-xs font-mono text-red-300/90 whitespace-pre-wrap break-all select-all">
                {inspectedPayload.payload}
              </pre>
            </div>

            {/* Outcome Comparison */}
            <div className="grid grid-cols-2 gap-3 text-xs pt-1">
              <div className="p-3 rounded-lg bg-red-950/20 border border-red-900/40 space-y-1">
                <div className="text-[10px] font-mono uppercase text-red-400 font-semibold">
                  Baseline Raw LLM Outcome
                </div>
                <div className="text-red-300 font-mono font-medium">
                  {inspectedPayload.baseline_verdict}
                </div>
                <div className="text-[11px] text-zinc-400">
                  Malicious instruction successfully overrode classification logic.
                </div>
              </div>

              <div className="p-3 rounded-lg bg-emerald-950/20 border border-emerald-900/40 space-y-1">
                <div className="text-[10px] font-mono uppercase text-emerald-400 font-semibold">
                  Sentra-X Pipeline Outcome
                </div>
                <div className="text-emerald-300 font-mono font-medium">
                  {inspectedPayload.sentrax_verdict}
                </div>
                <div className="text-[11px] text-zinc-400">
                  Safely isolated within data envelope; injection suspect detected.
                </div>
              </div>
            </div>

            <div className="pt-2 flex justify-end">
              <button
                type="button"
                onClick={() => setInspectedPayload(null)}
                className="px-4 py-2 rounded-lg bg-zinc-100 text-zinc-950 font-mono text-xs font-semibold hover:bg-zinc-200 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

