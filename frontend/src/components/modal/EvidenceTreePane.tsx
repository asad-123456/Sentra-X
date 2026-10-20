import React, { useState, useEffect, useRef } from 'react';
import type { EvidencePack } from '../../types/sentrax';
import {
  FileText,
  Code2,
  ShieldCheck,
  Copy,
  Check,
  ChevronDown,
  ChevronRight,
  Sparkles,
} from 'lucide-react';

interface EvidenceTreePaneProps {
  evidencePack: EvidencePack;
  citedEvidenceKeys: string[];
  selectedCitationKey: string | null;
}

type EvidenceTab = 'tree' | 'raw_json' | 'prompt_envelope';

// Dot-notation & bracket-index key resolver matching backend/app/services/evidence_assembler.py
const TOKEN = /([^.\[\]]+)|\[(\d+)\]/g;

export function resolveKey(pack: unknown, key: string): unknown | undefined {
  let cur: any = pack;
  for (const m of key.matchAll(TOKEN)) {
    const [, name, index] = m;
    if (name !== undefined) {
      if (cur === null || typeof cur !== 'object' || Array.isArray(cur) || !(name in cur)) return undefined;
      cur = cur[name];
    } else {
      const i = Number(index);
      if (!Array.isArray(cur) || i >= cur.length) return undefined;
      cur = cur[i];
    }
  }
  return cur;
}

export const EvidenceTreePane: React.FC<EvidenceTreePaneProps> = ({
  evidencePack,
  citedEvidenceKeys,
  selectedCitationKey,
}) => {
  const [activeTab, setActiveTab] = useState<EvidenceTab>('tree');
  const [copiedRaw, setCopiedRaw] = useState(false);
  const [copiedEnvelope, setCopiedEnvelope] = useState(false);
  const [collapsedNodes, setCollapsedNodes] = useState<Record<string, boolean>>({});

  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-switch to tree tab and scroll to element when selectedCitationKey is clicked
  useEffect(() => {
    if (!selectedCitationKey) return;

    // Slight delay to allow DOM transition
    const timeout = setTimeout(() => {
      setActiveTab('tree');
      if (!containerRef.current) return;
      const targetElement = containerRef.current.querySelector(
        `[data-dot-key="${CSS.escape(selectedCitationKey)}"]`
      );
      if (targetElement) {
        targetElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 50);

    return () => clearTimeout(timeout);
  }, [selectedCitationKey]);

  const toggleCollapse = (path: string) => {
    setCollapsedNodes((prev) => ({
      ...prev,
      [path]: !prev[path],
    }));
  };

  const handleCopyRaw = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(evidencePack, null, 2));
      setCopiedRaw(true);
      setTimeout(() => setCopiedRaw(false), 2000);
    } catch (err) {
      console.error('Failed to copy JSON:', err);
    }
  };

  const handleCopyEnvelope = async () => {
    try {
      const envelope = {
        _security_context: {
          envelope_id: `env-${evidencePack.id}`,
          sanitized_at: evidencePack.created_at,
          injection_suspect: evidencePack.injection_suspect,
          delimiter_policy: 'STRICT_XML_ISOLATION_STRIPPED',
        },
        read_only_telemetry_payload: evidencePack.telemetry_payload,
        asset_context: evidencePack.asset_context,
        alert_metadata: evidencePack.alert_metadata,
      };
      await navigator.clipboard.writeText(JSON.stringify(envelope, null, 2));
      setCopiedEnvelope(true);
      setTimeout(() => setCopiedEnvelope(false), 2000);
    } catch (err) {
      console.error('Failed to copy envelope:', err);
    }
  };

  // Recursive Tree Node Renderer supporting dot-notation, list leaves, and bracket indexes
  const renderTreeNode = (key: string, value: unknown, currentPath: string, depth = 0) => {
    const isArray = Array.isArray(value);
    const isObject = value !== null && typeof value === 'object';
    const isArrayOfPrimitives =
      isArray && value.every((v) => v === null || typeof v !== 'object');
    const isContainer = isObject && !isArrayOfPrimitives;

    const isCited = citedEvidenceKeys.some(
      (k) =>
        k === currentPath ||
        k.startsWith(currentPath + '.') ||
        k.startsWith(currentPath + '[')
    );
    const isSelected = selectedCitationKey === currentPath;
    const isCollapsed = Boolean(collapsedNodes[currentPath]);

    if (isContainer) {
      const keys = isArray
        ? Array.from({ length: value.length }, (_, i) => i)
        : Object.keys(value as Record<string, unknown>);

      return (
        <div key={currentPath} className="space-y-1">
          <div
            data-dot-key={currentPath}
            onClick={() => toggleCollapse(currentPath)}
            className={`flex items-center gap-1.5 py-1 px-2 rounded-md hover:bg-zinc-900/60 cursor-pointer text-xs font-mono select-none transition-colors ${
              isSelected
                ? 'bg-cyan-950/50 ring-1 ring-cyan-400 border-l-2 border-l-cyan-400 pl-1.5'
                : isCited
                ? 'bg-zinc-900/80 border-l-2 border-l-cyan-400 pl-1.5'
                : ''
            }`}
            style={{ marginLeft: `${depth * 14}px` }}
          >
            {isCollapsed ? (
              <ChevronRight className="size-3.5 text-zinc-500 shrink-0" />
            ) : (
              <ChevronDown className="size-3.5 text-zinc-400 shrink-0" />
            )}
            <span className="font-semibold text-zinc-300">{key}</span>
            <span className="text-[10px] text-zinc-600 font-normal">
              ({keys.length} {keys.length === 1 ? 'item' : 'items'})
            </span>

            {isCited && (
              <span className="ml-auto inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-bold font-mono tracking-wider bg-cyan-950/80 text-cyan-300 border border-cyan-700/80">
                <Sparkles className="size-2.5 text-cyan-400" />
                <span>CITED BY AI</span>
              </span>
            )}
          </div>

          {!isCollapsed && (
            <div className="space-y-1">
              {isArray
                ? (value as unknown[]).map((subVal, idx) =>
                    renderTreeNode(
                      `[${idx}]`,
                      subVal,
                      `${currentPath}[${idx}]`,
                      depth + 1
                    )
                  )
                : (keys as string[]).map((subKey) =>
                    renderTreeNode(
                      subKey,
                      (value as Record<string, unknown>)[subKey],
                      `${currentPath}.${subKey}`,
                      depth + 1
                    )
                  )}
            </div>
          )}
        </div>
      );
    }

    // Leaf Value Node (handles primitives and lists of plain values as single citable leaf)
    return (
      <div
        key={currentPath}
        data-dot-key={currentPath}
        className={`flex flex-col sm:flex-row sm:items-baseline justify-between gap-2 py-1.5 px-2.5 rounded-lg text-xs font-mono transition-all ${
          isSelected
            ? 'bg-cyan-950/60 border border-cyan-500 shadow-[0_0_12px_rgba(6,182,212,0.25)] ring-1 ring-cyan-400'
            : isCited
            ? 'bg-zinc-900/90 border border-cyan-900/60 border-l-2 border-l-cyan-400'
            : 'hover:bg-zinc-900/40 border border-transparent'
        }`}
        style={{ marginLeft: `${depth * 14}px` }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-zinc-400 font-medium shrink-0">{key}:</span>
          <span className="text-zinc-100 break-all select-all font-mono">
            {isArrayOfPrimitives
              ? JSON.stringify(value)
              : typeof value === 'boolean'
              ? String(value)
              : typeof value === 'string'
              ? `"${value}"`
              : value === null
              ? 'null'
              : String(value)}
          </span>
        </div>

        <div className="flex items-center gap-2 shrink-0 self-end sm:self-auto">
          {isCited && (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-bold font-mono tracking-wider bg-cyan-950 text-cyan-300 border border-cyan-700/80">
              <Sparkles className="size-2.5 text-cyan-400" />
              <span>CITED BY AI</span>
            </span>
          )}
          <span className="text-[10px] text-zinc-600 font-mono hidden md:inline">
            {currentPath}
          </span>
        </div>
      </div>
    );
  };

  return (
    <div className="h-full flex flex-col min-h-0 bg-zinc-950 border-l border-zinc-800/80 text-zinc-100 text-xs overflow-hidden">
      {/* 3 Sub-Tabs Header */}
      <div className="h-12 border-b border-zinc-800/80 bg-zinc-900/50 px-4 flex items-center justify-between gap-3 shrink-0">
        <div className="flex items-center gap-1.5 p-1 bg-zinc-950 rounded-lg border border-zinc-800/80">
          <button
            type="button"
            onClick={() => setActiveTab('tree')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-mono font-medium transition-colors ${
              activeTab === 'tree'
                ? 'bg-zinc-800 text-zinc-100 shadow-sm border border-zinc-700'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <FileText className="size-3.5 text-zinc-400" />
            <span>Evidence Tree</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('raw_json')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-mono font-medium transition-colors ${
              activeTab === 'raw_json'
                ? 'bg-zinc-800 text-zinc-100 shadow-sm border border-zinc-700'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <Code2 className="size-3.5 text-zinc-400" />
            <span>Raw Log JSON</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('prompt_envelope')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-mono font-medium transition-colors ${
              activeTab === 'prompt_envelope'
                ? 'bg-zinc-800 text-zinc-100 shadow-sm border border-zinc-700'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <ShieldCheck className="size-3.5 text-cyan-400" />
            <span>Prompt Envelope</span>
          </button>
        </div>

        {/* Action button for active tab */}
        {activeTab === 'raw_json' && (
          <button
            type="button"
            onClick={handleCopyRaw}
            className="flex items-center gap-1.5 px-2.5 py-1 bg-zinc-900 hover:bg-zinc-850 border border-zinc-750 rounded text-xs font-mono text-zinc-300 hover:text-white transition-colors cursor-pointer"
            title="Copy full Wazuh JSON to clipboard"
          >
            {copiedRaw ? (
              <>
                <Check className="size-3 text-emerald-400" />
                <span className="text-emerald-400">Copied!</span>
              </>
            ) : (
              <>
                <Copy className="size-3 text-zinc-400" />
                <span>Copy JSON</span>
              </>
            )}
          </button>
        )}

        {activeTab === 'prompt_envelope' && (
          <button
            type="button"
            onClick={handleCopyEnvelope}
            className="flex items-center gap-1.5 px-2.5 py-1 bg-zinc-900 hover:bg-zinc-850 border border-zinc-750 rounded text-xs font-mono text-zinc-300 hover:text-white transition-colors cursor-pointer"
            title="Copy sanitized envelope to clipboard"
          >
            {copiedEnvelope ? (
              <>
                <Check className="size-3 text-emerald-400" />
                <span className="text-emerald-400">Copied!</span>
              </>
            ) : (
              <>
                <Copy className="size-3 text-zinc-400" />
                <span>Copy Envelope</span>
              </>
            )}
          </button>
        )}
      </div>

      {/* Pane Content Body */}
      <div ref={containerRef} className="flex-1 min-h-0 overflow-y-auto p-4 custom-scrollbar">
        {activeTab === 'tree' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between text-[11px] text-zinc-400 font-mono pb-2 border-b border-zinc-900">
              <span>Telemetry Evidence</span>
              <span className="text-cyan-400">
                {citedEvidenceKeys.length} cited fields highlighted
              </span>
            </div>

            {/* Tree Sections */}
            <div className="space-y-3">
              {renderTreeNode('alert_metadata', evidencePack.alert_metadata, 'alert_metadata')}
              {renderTreeNode('asset_context', evidencePack.asset_context, 'asset_context')}
              {renderTreeNode('telemetry_payload', evidencePack.telemetry_payload, 'telemetry_payload')}
              {evidencePack.temporal_context && evidencePack.temporal_context.length > 0 && (
                renderTreeNode('temporal_context', evidencePack.temporal_context, 'temporal_context')
              )}
            </div>
          </div>
        )}

        {activeTab === 'raw_json' && (
          <div className="space-y-2 flex flex-col h-full min-h-0">
            <div className="flex items-center justify-between text-[11px] text-zinc-400 font-mono pb-1 shrink-0">
              <span>RAW WAZUH TELEMETRY &amp; SYSMON EVENT LOG</span>
              <span className="text-zinc-500">Read-Only JSON</span>
            </div>
            <pre
              tabIndex={0}
              className="flex-1 min-h-[350px] max-h-[calc(92vh-220px)] p-4 rounded-xl bg-black border border-zinc-800 text-zinc-300 font-mono text-xs overflow-x-auto overflow-y-auto custom-scrollbar leading-relaxed select-text focus:outline-none focus:ring-1 focus:ring-zinc-700"
            >
              {JSON.stringify(evidencePack, null, 2)}
            </pre>
          </div>
        )}

        {activeTab === 'prompt_envelope' && (
          <div className="space-y-3 flex flex-col h-full min-h-0">
            <div className="p-3.5 rounded-xl bg-cyan-950/20 border border-cyan-800/40 text-cyan-200 text-xs font-sans space-y-1 shrink-0">
              <div className="font-semibold text-cyan-300 flex items-center gap-1.5 font-mono text-xs">
                <ShieldCheck className="size-4" />
                <span>Isolated Prompt Envelope Preview</span>
              </div>
              <p className="text-[11px] text-zinc-400">
                Demonstrates how raw user/host telemetry is sanitized, stripped of adversarial delimiter strings, and quarantined inside read-only XML/JSON tags prior to LLM evaluation.
              </p>
            </div>

            <pre
              tabIndex={0}
              className="flex-1 min-h-[300px] max-h-[calc(92vh-280px)] p-4 rounded-xl bg-black border border-zinc-800 text-cyan-100 font-mono text-xs overflow-x-auto overflow-y-auto custom-scrollbar leading-relaxed select-text focus:outline-none focus:ring-1 focus:ring-cyan-900"
            >
              {JSON.stringify(
                {
                  _security_context: {
                    envelope_id: `env-${evidencePack.id}`,
                    sanitized_at: evidencePack.created_at,
                    injection_suspect: evidencePack.injection_suspect,
                    delimiter_policy: 'STRICT_XML_ISOLATION_STRIPPED',
                  },
                  read_only_telemetry_payload: evidencePack.telemetry_payload,
                  asset_context: evidencePack.asset_context,
                  alert_metadata: evidencePack.alert_metadata,
                },
                null,
                2
              )}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
};
