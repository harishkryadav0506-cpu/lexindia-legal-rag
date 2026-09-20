"use client";

import React, { useState } from "react";
import {
  FileText,
  Activity,
  ExternalLink,
  Clock,
} from "lucide-react";
import { CitationItem, AgentTraceItem } from "@/types";

interface SourcesPanelProps {
  citations: CitationItem[];
  agentTrace: AgentTraceItem[];
  onSelectCitation: (chunk: CitationItem) => void;
}

export default function SourcesPanel({
  citations,
  agentTrace,
  onSelectCitation,
}: SourcesPanelProps) {
  const [activeTab, setActiveTab] = useState<"chunks" | "trace">("chunks");

  const getAuthorityLabel = (level?: number) => {
    switch (level) {
      case 1:
        return { label: "Act / Statute", color: "bg-amber-950/60 text-amber-300 border-amber-800/60" };
      case 2:
        return { label: "Rules", color: "bg-blue-950/60 text-blue-300 border-blue-800/60" };
      case 3:
        return { label: "Circular", color: "bg-purple-950/60 text-purple-300 border-purple-800/60" };
      case 4:
        return { label: "Instructions", color: "bg-teal-950/60 text-teal-300 border-teal-800/60" };
      default:
        return { label: "Statutory", color: "bg-slate-800 text-slate-300 border-slate-700" };
    }
  };

  return (
    <div className="glass-panel rounded-2xl border border-slate-800 shadow-xl overflow-hidden">
      {/* Tab Switcher */}
      <div className="flex border-b border-slate-800 bg-slate-950/60">
        <button
          onClick={() => setActiveTab("chunks")}
          className={`flex-1 py-3 px-4 text-xs font-semibold flex items-center justify-center gap-2 border-b-2 transition-colors ${
            activeTab === "chunks"
              ? "border-amber-400 text-amber-400 bg-slate-900/40"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <FileText className="w-4 h-4" />
          <span>Retrieved Statutory Corpus ({citations.length})</span>
        </button>

        <button
          onClick={() => setActiveTab("trace")}
          className={`flex-1 py-3 px-4 text-xs font-semibold flex items-center justify-center gap-2 border-b-2 transition-colors ${
            activeTab === "trace"
              ? "border-amber-400 text-amber-400 bg-slate-900/40"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Activity className="w-4 h-4" />
          <span>Multi-Agent Execution Trace ({agentTrace.length})</span>
        </button>
      </div>

      {/* Tab 1: Retrieved Chunks Table */}
      {activeTab === "chunks" && (
        <div className="p-4 sm:p-6 overflow-x-auto">
          {citations.length === 0 ? (
            <p className="text-slate-500 text-xs text-center py-6">No chunks retrieved.</p>
          ) : (
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 font-medium">
                  <th className="py-2.5 px-3">#</th>
                  <th className="py-2.5 px-3">Section / Provision</th>
                  <th className="py-2.5 px-3">Authority Level</th>
                  <th className="py-2.5 px-3">Doc Type</th>
                  <th className="py-2.5 px-3" title="Statutory Authority-Weighted Retrieval Score">Auth-Weighted Score</th>
                  <th className="py-2.5 px-3">Origin</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {citations.map((c, i) => {
                  const auth = getAuthorityLabel(c.authority_level);
                  return (
                    <tr key={i} className="hover:bg-slate-900/40 transition-colors">
                      <td className="py-3 px-3 font-mono text-amber-400 font-bold">
                        {c.citation_id || `[C${i + 1}]`}
                      </td>
                      <td className="py-3 px-3 font-medium text-slate-200">
                        {c.section_id}
                        {c.page_number ? (
                          <span className="text-slate-500 text-[11px] ml-1.5 font-normal">
                            (Page {c.page_number})
                          </span>
                        ) : null}
                      </td>
                      <td className="py-3 px-3">
                        <span className={`px-2 py-0.5 rounded text-[11px] font-semibold border ${auth.color}`}>
                          {auth.label}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-slate-400 capitalize">
                        {c.doc_type || "statute"}
                      </td>
                      <td className="py-3 px-3 font-mono text-slate-300">
                        {c.score ? c.score.toFixed(4) : "—"}
                      </td>
                      <td className="py-3 px-3">
                        {c.graph_expanded ? (
                          <span className="text-[10px] bg-purple-950 text-purple-300 px-1.5 py-0.5 rounded border border-purple-800">
                            Graph 2-Hop
                          </span>
                        ) : (
                          <span className="text-[10px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded border border-slate-700">
                            Hybrid RRF
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-3 text-right">
                        <button
                          onClick={() => onSelectCitation(c)}
                          className="text-amber-400 hover:text-amber-300 font-medium text-xs flex items-center gap-1 justify-end ml-auto group"
                        >
                          <span>Inspect</span>
                          <ExternalLink className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Tab 2: Agent Execution Trace */}
      {activeTab === "trace" && (
        <div className="p-4 sm:p-6 space-y-4">
          {agentTrace.length === 0 ? (
            <p className="text-slate-500 text-xs text-center py-6">No agent trace available.</p>
          ) : (
            <div className="relative border-l-2 border-slate-800 ml-4 space-y-6">
              {agentTrace.map((entry, idx) => (
                <div key={idx} className="relative pl-6">
                  {/* Timeline bullet */}
                  <div className="absolute -left-[9px] top-1.5 w-4 h-4 rounded-full bg-slate-950 border-2 border-amber-400 flex items-center justify-center">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                  </div>

                  <div className="bg-slate-900/80 rounded-xl p-3.5 border border-slate-800 space-y-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-amber-400">{entry.agent}</span>
                        <span className="text-xs text-slate-300 font-medium">{entry.action}</span>
                      </div>
                      <span className="text-[11px] font-mono text-slate-500 flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {entry.latency_ms} ms
                      </span>
                    </div>

                    {/* Inputs & Outputs Summary */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs pt-1">
                      <div className="bg-slate-950/60 p-2 rounded border border-slate-800/80">
                        <span className="text-slate-500 font-semibold block mb-0.5 text-[10px] uppercase">
                          Inputs:
                        </span>
                        <p className="text-slate-300 font-mono break-all">{entry.inputs_summary || "—"}</p>
                      </div>

                      <div className="bg-slate-950/60 p-2 rounded border border-slate-800/80">
                        <span className="text-slate-500 font-semibold block mb-0.5 text-[10px] uppercase">
                          Outputs:
                        </span>
                        <p className="text-slate-300 font-mono break-all">{entry.outputs_summary || "—"}</p>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
