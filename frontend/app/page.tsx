"use client";

import React, { useState } from "react";
import Navbar from "@/components/Navbar";
import QueryInput from "@/components/QueryInput";
import AnswerCard from "@/components/AnswerCard";
import SourcesPanel from "@/components/SourcesPanel";
import CitationGraphViewer from "@/components/CitationGraphViewer";
import PdfProvenanceModal from "@/components/PdfProvenanceModal";
import { QueryRequest, QueryResponse, CitationItem } from "@/types";
import { sendQuery } from "@/lib/api";
import { BookOpen, ShieldAlert, Sparkles, AlertCircle } from "lucide-react";

export default function HomePage() {
  const [loading, setLoading] = useState<boolean>(false);
  const [queryResponse, setQueryResponse] = useState<QueryResponse | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<CitationItem | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleQuerySubmit = async (req: QueryRequest) => {
    setLoading(true);
    setErrorMessage(null);
    try {
      const response = await sendQuery(req);
      setQueryResponse(response);
      // P13 / FIX 12: Trigger Navbar badge update on query completed
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("lexindia:query_completed"));
      }
    } catch (err: any) {
      console.error("Query failed:", err);
      setErrorMessage(
        err?.message || "An unexpected error occurred while processing your legal research query."
      );
    } finally {
      setLoading(false);
    }
  };

  // Find primary section ID to center graph if citations exist
  const primarySection =
    queryResponse?.citations && queryResponse.citations.length > 0
      ? queryResponse.citations[0].section_id
      : "Section 80C";

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100 selection:bg-amber-500/30 selection:text-amber-200">
      <Navbar />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Hero Section */}
        <div className="text-center space-y-3 max-w-3xl mx-auto pt-2 pb-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs font-semibold uppercase tracking-wider">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Authoritative Statutory Intelligence</span>
          </div>
          <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-slate-100 font-serif">
            Indian Tax Law <span className="text-amber-400">Research Portal</span>
          </h1>
          <p className="text-sm sm:text-base text-slate-400 max-w-2xl mx-auto leading-relaxed">
            Strict cite-or-refuse legal RAG powered by the Income Tax Act 1961, Income Tax Rules 1962,
            Finance Acts, and CBDT circulars with verified citation graph expansion.
          </p>
        </div>

        {/* Query Input Section */}
        <div className="max-w-4xl mx-auto">
          <QueryInput onSubmit={handleQuerySubmit} isLoading={loading} />
        </div>

        {/* Error Alert */}
        {errorMessage && (
          <div className="max-w-4xl mx-auto bg-rose-950/40 border border-rose-800/80 rounded-2xl p-4 flex items-start gap-3 text-rose-300">
            <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <h4 className="font-bold text-sm">Query Execution Failed</h4>
              <p className="text-xs font-mono text-rose-300/90">{errorMessage}</p>
            </div>
          </div>
        )}

        {/* Results Area */}
        {queryResponse && (
          <div className="space-y-8 max-w-6xl mx-auto animate-in fade-in duration-300">
            {/* Primary Answer Card */}
            <div>
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-amber-400" />
                <span>Statutory Research Findings</span>
              </h2>
              <AnswerCard
                data={queryResponse}
                onSelectCitation={(c) => setSelectedCitation(c)}
              />
            </div>

            {/* Statutory Sources & Multi-Agent Trace */}
            <div>
              <SourcesPanel
                citations={queryResponse.citations || []}
                agentTrace={queryResponse.agent_trace || []}
                onSelectCitation={(c) => setSelectedCitation(c)}
              />
            </div>

            {/* Interactive Cytoscape Citation Graph */}
            <div>
              <CitationGraphViewer initialSectionId={primarySection} />
            </div>
          </div>
        )}

        {/* Empty State / Feature Highlights (When no query is run yet) */}
        {!queryResponse && !loading && (
          <div className="max-w-4xl mx-auto grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4">
            <div className="bg-slate-900/40 border border-slate-800/80 rounded-xl p-5 space-y-2 hover:border-slate-700 transition-colors">
              <div className="w-8 h-8 rounded-lg bg-amber-500/10 text-amber-400 flex items-center justify-center font-bold">
                1
              </div>
              <h3 className="text-sm font-bold text-slate-200">100% Real Legal Corpus</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Ingested directly from official government gazettes, indiacode.gov.in, and incometaxindia.gov.in.
              </p>
            </div>

            <div className="bg-slate-900/40 border border-slate-800/80 rounded-xl p-5 space-y-2 hover:border-slate-700 transition-colors">
              <div className="w-8 h-8 rounded-lg bg-purple-500/10 text-purple-400 flex items-center justify-center font-bold">
                2
              </div>
              <h3 className="text-sm font-bold text-slate-200">Graph Expansion</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                2-hop network traversal over statutory cross-references (read with, subject to, amended by).
              </p>
            </div>

            <div className="bg-slate-900/40 border border-slate-800/80 rounded-xl p-5 space-y-2 hover:border-slate-700 transition-colors">
              <div className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center font-bold">
                3
              </div>
              <h3 className="text-sm font-bold text-slate-200">Human-In-The-Loop</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Low confidence or complex queries are routed to legal review queue with LangGraph checkpointer.
              </p>
            </div>
          </div>
        )}
      </main>

      {/* Statutory Footer */}
      <footer className="border-t border-slate-800/80 bg-slate-950 py-6 text-center text-xs text-slate-500 px-4">
        <div className="max-w-4xl mx-auto space-y-2">
          <p className="flex items-center justify-center gap-1.5 text-amber-400/80 font-medium">
            <ShieldAlert className="w-4 h-4 text-amber-400" />
            <span>Statutory Disclaimer</span>
          </p>
          <p className="text-[11px] leading-relaxed text-slate-500 max-w-2xl mx-auto">
            LexIndia is an automated statutory research system built exclusively on official Indian tax laws,
            rules, and circulars. The system operates on strict cite-or-refuse guidelines. Output does not
            constitute legal or financial advice. Consult a certified Chartered Accountant or legal practitioner
            for official filing decisions.
          </p>
          <p className="text-[10px] text-slate-600 pt-1">
            LexIndia © 2026 — Indian Tax Law Research Engine
          </p>
        </div>
      </footer>

      {/* PDF Provenance Side-drawer Modal */}
      <PdfProvenanceModal
        citation={selectedCitation}
        onClose={() => setSelectedCitation(null)}
      />
    </div>
  );
}
