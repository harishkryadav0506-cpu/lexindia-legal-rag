"use client";

import React from "react";
import { X, ExternalLink, ShieldCheck, BookOpen } from "lucide-react";
import { CitationItem } from "@/types";

interface PdfProvenanceModalProps {
  citation: CitationItem | null;
  onClose: () => void;
}

export default function PdfProvenanceModal({
  citation,
  onClose,
}: PdfProvenanceModalProps) {
  if (!citation) return null;

  const targetUrl = citation.page_number
    ? `${citation.source_url}#page=${citation.page_number}`
    : citation.source_url;

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex justify-end">
      {/* Side Drawer Panel */}
      <div className="w-full max-w-xl h-full bg-slate-900 border-l border-slate-700 shadow-2xl flex flex-col animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-slate-950/50">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-amber-500/20 border border-amber-500/30 flex items-center justify-center">
              <BookOpen className="w-4 h-4 text-amber-400" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                <span>{citation.section_id}</span>
                {citation.citation_id && (
                  <span className="text-xs font-mono text-amber-400">{citation.citation_id}</span>
                )}
              </h3>
              <p className="text-xs text-slate-400">Official Statutory Source Provenance</p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5 text-sm">
          {/* Metadata Card */}
          <div className="bg-slate-950/60 rounded-xl p-4 border border-slate-800 space-y-2.5">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400">Document Type:</span>
              <span className="text-slate-200 font-semibold capitalize">
                {citation.doc_type || "Statute"}
              </span>
            </div>

            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400">Document Page:</span>
              <span className="text-amber-400 font-mono font-semibold">
                Page {citation.page_number || 1}
              </span>
            </div>

            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400">Relevance Score:</span>
              <span className="text-slate-200 font-mono">
                {citation.score ? citation.score.toFixed(4) : "—"}
              </span>
            </div>

            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400">Retrieval Mechanism:</span>
              <span className="text-slate-200">
                {citation.graph_expanded ? "2-Hop Graph Expansion" : "Hybrid BM25 + BGE Rerank"}
              </span>
            </div>

            <div className="pt-2 border-t border-slate-800/80 flex items-center gap-1.5 text-xs text-emerald-400 font-medium">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>Authentic Official Government Document</span>
            </div>
          </div>

          {/* Chunk Text Content */}
          <div className="space-y-2">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Statutory Text (Extracted Chunk):
            </h4>
            <div className="bg-slate-950 rounded-xl p-4 border border-slate-800 font-serif leading-relaxed text-slate-200 text-xs sm:text-sm whitespace-pre-wrap max-h-96 overflow-y-auto shadow-inner">
              {citation.text || "Text extracted directly from official PDF corpus."}
            </div>
          </div>

          {/* Source URL Box */}
          <div className="space-y-1 text-xs">
            <span className="text-slate-400 block font-medium">Official Government Source URL:</span>
            <p className="bg-slate-950 p-2.5 rounded-lg border border-slate-800 font-mono text-[11px] text-amber-300 break-all select-all">
              {citation.source_url}
            </p>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/80 flex items-center justify-between gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold transition-colors"
          >
            Close
          </button>

          <a
            href={targetUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="px-5 py-2 bg-amber-500 hover:bg-amber-400 text-slate-950 rounded-xl text-xs font-bold transition-all shadow-lg shadow-amber-500/20 flex items-center gap-2"
          >
            <span>Open Official PDF at Page {citation.page_number || 1}</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </div>
    </div>
  );
}
