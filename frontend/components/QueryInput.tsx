"use client";

import React, { useState } from "react";
import { Sparkles, UserCheck, ArrowRight, Loader2 } from "lucide-react";
import { QueryRequest } from "@/types";

interface QueryInputProps {
  onSubmit: (req: QueryRequest) => void;
  isLoading: boolean;
}

const SAMPLE_QUERIES = [
  "Can I claim both HRA and home loan interest deduction?",
  "old vs new regime for 15 lakh income FY 2025-26",
  "What are the turnover limits for tax audit under Section 44AB?",
  "kya main apne rent ka deduction le sakta hu?",
];

export default function QueryInput({ onSubmit, isLoading }: QueryInputProps) {
  const [question, setQuestion] = useState("");
  const [financialYear, setFinancialYear] = useState("2024-25");
  const [taxpayerType, setTaxpayerType] = useState("Individual (Salaried)");
  const [requireReview, setRequireReview] = useState(false);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!question.trim() || isLoading) return;

    // Deterministically read checkbox DOM state at submit time to prevent stale closure state
    const checkboxEl = typeof document !== "undefined"
      ? (document.getElementById("require-review-toggle") as HTMLInputElement | null)
      : null;
    const isChecked = checkboxEl !== null ? Boolean(checkboxEl.checked) : Boolean(requireReview);

    onSubmit({
      question: question.trim(),
      financial_year: financialYear,
      taxpayer_type: taxpayerType,
      require_review: isChecked,
    });
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="glass-panel-glow rounded-2xl p-4 sm:p-6 shadow-xl relative overflow-hidden">
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Search Textarea */}
        <div className="relative">
          <textarea
            id="query-input"
            rows={3}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask any statutory question on Income Tax Act, 1961, IT Rules 1962, Finance Acts, or CBDT circulars... (Ctrl+Enter to submit)"
            className="w-full bg-slate-900/90 text-slate-100 placeholder-slate-500 rounded-xl px-4 py-3 border border-slate-700/80 focus:outline-none focus:ring-2 focus:ring-amber-400/50 focus:border-amber-400 text-sm sm:text-base resize-none transition-all shadow-inner"
            disabled={isLoading}
          />
        </div>

        {/* Suggestion Chips */}
        <div className="flex flex-wrap items-center gap-1.5 text-xs text-slate-400">
          <span className="flex items-center gap-1 text-amber-400/80 font-medium mr-1">
            <Sparkles className="w-3.5 h-3.5" /> Suggestions:
          </span>
          {SAMPLE_QUERIES.map((sample, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => setQuestion(sample)}
              className="bg-slate-800/80 hover:bg-slate-700/90 text-slate-300 hover:text-white px-2.5 py-1 rounded-lg border border-slate-700/60 transition-colors text-left"
            >
              {sample}
            </button>
          ))}
        </div>

        {/* Context Controls Row */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2 border-t border-slate-800/60">
          {/* Financial Year Selector */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">
              Assessment / Financial Year
            </label>
            <select
              id="fy-selector"
              value={financialYear}
              onChange={(e) => setFinancialYear(e.target.value)}
              className="w-full bg-slate-900 text-slate-200 border border-slate-700 rounded-lg px-3 py-2 text-xs focus:ring-1 focus:ring-amber-400 focus:outline-none"
            >
              <option value="2026-27">FY 2026-27 (AY 2027-28)</option>
              <option value="2025-26">FY 2025-26 (AY 2026-27)</option>
              <option value="2024-25">FY 2024-25 (AY 2025-26)</option>
              <option value="2023-24">FY 2023-24 (AY 2024-25)</option>
              <option value="2022-23">FY 2022-23 (AY 2023-24)</option>
            </select>
          </div>

          {/* Taxpayer Classification */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">
              Taxpayer Classification
            </label>
            <select
              id="taxpayer-selector"
              value={taxpayerType}
              onChange={(e) => setTaxpayerType(e.target.value)}
              className="w-full bg-slate-900 text-slate-200 border border-slate-700 rounded-lg px-3 py-2 text-xs focus:ring-1 focus:ring-amber-400 focus:outline-none"
            >
              <option value="Individual (Salaried)">Individual (Salaried)</option>
              <option value="Individual (Self-Employed / Business)">Individual (Self-Employed / Business)</option>
              <option value="Non-Resident Indian (NRI)">Non-Resident Indian (NRI)</option>
              <option value="Senior Citizen (Age 60+)">Senior Citizen (Age 60+)</option>
            </select>
          </div>

          {/* Human Review Toggle */}
          <div className="flex flex-col justify-end">
            <label className="flex items-center gap-2 cursor-pointer select-none bg-slate-900/60 hover:bg-slate-900 px-3 py-2 rounded-lg border border-slate-700/80 transition-colors">
              <input
                id="require-review-toggle"
                type="checkbox"
                checked={requireReview}
                onChange={(e) => setRequireReview(e.target.checked)}
                className="w-4 h-4 rounded text-amber-500 bg-slate-800 border-slate-600 focus:ring-amber-400 focus:ring-offset-slate-900"
              />
              <div className="flex items-center gap-1.5 text-xs text-slate-300">
                <UserCheck className="w-3.5 h-3.5 text-amber-400" />
                <span>Request expert review</span>
              </div>
            </label>
          </div>
        </div>

        {/* Submit Button */}
        <div className="flex justify-end pt-1">
          <button
            id="search-btn"
            type="submit"
            disabled={!question.trim() || isLoading}
            className="w-full sm:w-auto px-6 py-2.5 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-semibold rounded-xl text-sm transition-all shadow-lg shadow-amber-500/20 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Searching Law Corpus...</span>
              </>
            ) : (
              <>
                <span>Execute Legal Research</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
