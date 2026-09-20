"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import Link from "next/link";
import {
  ShieldCheck,
  AlertTriangle,
  Clock,
  ExternalLink,
  Copy,
  Check,
  Bot,
  Inbox,
  Bookmark,
} from "lucide-react";
import { QueryResponse, CitationItem } from "@/types";

interface AnswerCardProps {
  data: QueryResponse;
  onSelectCitation: (chunk: CitationItem) => void;
}

export default function AnswerCard({ data, onSelectCitation }: AnswerCardProps) {
  const [copied, setCopied] = useState(false);

  const rawText = data.final_answer || data.answer || data.draft_answer || "";
  let answerText = rawText;
  if (data.refused) {
    // P1 / Bug A Fix: Never render unhedged/fabricated content alongside refusal banner
    // Keep only the FY note (if present) and the clean refusal phrase + disclaimer
    const fyMatch = rawText.match(/^(Note:\s*Answer evaluated for selected Financial Year[^\n]*\n*)/i);
    const fyPrefix = fyMatch ? fyMatch[1].trim() + "\n\n" : "";
    answerText = `${fyPrefix}I cannot find sufficient authoritative guidance for this query.\n\n*LexIndia provides legal information, not professional tax advice.*`;
  }

  const isAwaiting = data.status === "awaiting_review";
  const confidencePercent = Math.round((data.confidence || 0) * 100);

  const handleCopy = () => {
    navigator.clipboard.writeText(answerText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="glass-panel rounded-2xl p-5 sm:p-7 border border-slate-700/80 shadow-2xl relative space-y-5">
      {/* Top Status & Telemetry Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-slate-800">
        <div className="flex flex-wrap items-center gap-2">
          {/* Route Badge */}
          <span className="px-2.5 py-1 rounded-md text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700 uppercase tracking-wider">
            {data.route}
          </span>

          {/* Confidence Badge */}
          <span
            className={`px-2.5 py-1 rounded-md text-xs font-semibold flex items-center gap-1.5 border ${
              confidencePercent >= 70
                ? "bg-emerald-950/60 text-emerald-400 border-emerald-800/60"
                : confidencePercent >= 50
                ? "bg-amber-950/60 text-amber-400 border-amber-800/60"
                : "bg-rose-950/60 text-rose-400 border-rose-800/60"
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>{confidencePercent}% Grounded</span>
          </span>

          {/* Fallback Used Badge */}
          {data.fallback_used && (
            <span className="px-2.5 py-1 rounded-md text-xs font-semibold bg-purple-950/60 text-purple-300 border border-purple-800/60 flex items-center gap-1">
              <Bot className="w-3.5 h-3.5 text-purple-400" />
              <span>Fallback: {data.fallback_model || "Gemini 3.6 Flash"}</span>
            </span>
          )}

          {/* Latency */}
          {data.latency_ms > 0 && (
            <span className="text-xs text-slate-500 flex items-center gap-1">
              <Clock className="w-3 h-3" />
              <span>{(data.latency_ms / 1000).toFixed(2)}s</span>
            </span>
          )}
        </div>

        {/* Copy Button */}
        <button
          onClick={handleCopy}
          className="text-xs text-slate-400 hover:text-slate-200 bg-slate-800 hover:bg-slate-700 px-3 py-1.5 rounded-lg border border-slate-700 transition-colors flex items-center gap-1.5"
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-emerald-400 font-medium">Copied</span>
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>

      {/* Awaiting Review Banner */}
      {isAwaiting && (
        <div className="bg-amber-950/40 border border-amber-600/40 rounded-xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-amber-200">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-amber-500/20 border border-amber-500/30 flex items-center justify-center shrink-0">
              <Inbox className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <h4 className="font-semibold text-sm text-amber-300">
                Awaiting Expert Legal Review
              </h4>
              <p className="text-xs text-amber-200/80">
                Thread ID: <code className="bg-amber-950/80 px-1 py-0.5 rounded text-amber-400">{data.thread_id}</code>
                {" — "}This draft is flagged for expert human verification before finalization.
              </p>
            </div>
          </div>
          <Link
            href="/review"
            className="shrink-0 px-4 py-1.5 bg-amber-500 hover:bg-amber-400 text-slate-950 rounded-lg text-xs font-bold transition-colors flex items-center gap-1"
          >
            <span>Open in Queue</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </Link>
        </div>
      )}

      {/* Refusal Banner */}
      {data.refused && (
        <div className="bg-rose-950/40 border border-rose-800/50 rounded-xl p-4 flex items-center gap-3 text-rose-200">
          <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0" />
          <div className="text-xs sm:text-sm">
            <span className="font-bold text-rose-300">Cite-or-Refuse Enforced: </span>
            The retrieved authoritative government documents do not provide sufficient evidentiary certainty to answer this query.
          </div>
        </div>
      )}

      {/* Answer Markdown Body */}
      <div className="prose-legal text-sm sm:text-base">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{answerText}</ReactMarkdown>
      </div>

      {/* Interactive Citation Chips */}
      {data.citations && data.citations.length > 0 && (
        <div className="pt-4 border-t border-slate-800">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2.5 flex items-center gap-1.5">
            <Bookmark className="w-3.5 h-3.5 text-amber-400" />
            <span>Authoritative Statutory Citations (Click to inspect source):</span>
          </h4>
          <div className="flex flex-wrap gap-2">
            {data.citations.map((c, idx) => {
              const chipId = c.citation_id || `[C${idx + 1}]`;
              return (
                <button
                  key={idx}
                  onClick={() => onSelectCitation(c)}
                  className="bg-slate-900/90 hover:bg-slate-800 text-slate-200 hover:text-amber-300 px-3 py-1.5 rounded-lg border border-slate-700 hover:border-amber-400/40 text-xs transition-all flex items-center gap-2 group shadow-sm"
                >
                  <span className="font-bold text-amber-400 group-hover:underline">
                    {chipId}
                  </span>
                  <span className="text-slate-300">{c.section_id}</span>
                  {c.page_number && (
                    <span className="text-slate-500 text-[11px]">p.{c.page_number}</span>
                  )}
                  {c.graph_expanded && (
                    <span className="text-[10px] bg-purple-950 text-purple-300 px-1 rounded border border-purple-800">
                      graph
                    </span>
                  )}
                  <ExternalLink className="w-3 h-3 text-slate-500 group-hover:text-amber-400 transition-colors" />
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
