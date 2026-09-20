"use client";

import React, { useState, useEffect } from "react";
import Navbar from "@/components/Navbar";
import {
  Inbox,
  CheckCircle2,
  Edit3,
  XCircle,
  Clock,
  AlertCircle,
  FileCheck,
  RefreshCw,
} from "lucide-react";
import { fetchPendingReviews, fetchReviewStats, submitReviewDecision } from "@/lib/api";
import { ReviewPendingItem, ReviewStatsResponse } from "@/types";

function formatAge(ageMinutes: number): string {
  if (ageMinutes < 1) return "just now";
  if (ageMinutes < 60) return `${Math.round(ageMinutes)}m ago`;
  const hours = ageMinutes / 60;
  if (hours < 24) return `${Math.round(hours)}h ago`;
  const days = hours / 24;
  if (days < 7) {
    const d = Math.round(days * 10) / 10;
    return `${d} ${d === 1 ? "day" : "days"} ago`;
  }
  return `${Math.round(days)} days ago`;
}

export default function ReviewQueuePage() {
  const [pending, setPending] = useState<ReviewPendingItem[]>([]);
  const [stats, setStats] = useState<ReviewStatsResponse | null>(null);
  const [selectedReview, setSelectedReview] = useState<ReviewPendingItem | null>(null);
  const [editedAnswer, setEditedAnswer] = useState("");
  const [reviewerNote, setReviewerNote] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const loadData = async () => {
    try {
      const [pendingList, statsData] = await Promise.all([
        fetchPendingReviews(),
        fetchReviewStats(),
      ]);
      setPending(pendingList);
      setStats(statsData);

      if (pendingList.length > 0 && !selectedReview) {
        setSelectedReview(pendingList[0]);
        setEditedAnswer(pendingList[0].draft_answer);
      }
    } catch (e) {
      console.error("Failed to load review data:", e);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSelect = (item: ReviewPendingItem) => {
    setSelectedReview(item);
    setEditedAnswer(item.draft_answer);
    setReviewerNote("");
    setFeedbackMsg(null);
  };

  const handleDecision = async (action: "approve" | "edit" | "reject") => {
    if (!selectedReview) return;
    setIsSubmitting(true);
    setFeedbackMsg(null);

    try {
      await submitReviewDecision(selectedReview.thread_id, {
        action,
        edited_answer: action === "edit" ? editedAnswer : undefined,
        reviewer_note: reviewerNote.trim() || undefined,
      });

      setFeedbackMsg({
        type: "success",
        text: `Decision '${action.toUpperCase()}' recorded successfully for thread ${selectedReview.thread_id}. Pair appended to verified dataset.`,
      });

      // Reload queue and stats
      const [newPending, newStats] = await Promise.all([
        fetchPendingReviews(),
        fetchReviewStats(),
      ]);
      setPending(newPending);
      setStats(newStats);

      if (newPending.length > 0) {
        setSelectedReview(newPending[0]);
        setEditedAnswer(newPending[0].draft_answer);
      } else {
        setSelectedReview(null);
      }
    } catch (err: any) {
      setFeedbackMsg({
        type: "error",
        text: `Error submitting decision: ${err.message}`,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100">
      <Navbar />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Page Header */}
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="p-1 rounded-md bg-amber-500/20 text-amber-400">
                <Inbox className="w-5 h-5" />
              </span>
              <h1 className="text-2xl font-bold tracking-tight text-slate-100">
                Human-in-the-Loop Review Queue
              </h1>
            </div>
            <p className="text-sm text-slate-400">
              Review, edit, or reject flagged answers. Approved edits become verified ground-truth pairs.
            </p>
          </div>

          <button
            onClick={loadData}
            className="px-3.5 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-700 rounded-lg text-xs font-medium text-slate-300 flex items-center gap-1.5 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh Queue</span>
          </button>
        </div>

        {/* Live HITL Stats Cards */}
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <div className="glass-panel p-3.5 rounded-xl border border-slate-800">
              <span className="text-xs text-slate-400 block font-medium">Pending Drafts</span>
              <span className="text-xl font-bold text-amber-400">{stats.pending_count}</span>
            </div>

            <div className="glass-panel p-3.5 rounded-xl border border-slate-800">
              <span className="text-xs text-slate-400 block font-medium">Total Decided</span>
              <span className="text-xl font-bold text-slate-200">{stats.total_decided}</span>
            </div>

            <div className="glass-panel p-3.5 rounded-xl border border-slate-800">
              <span className="text-xs text-slate-400 block font-medium">Approval Rate</span>
              <span className="text-xl font-bold text-emerald-400">
                {(stats.approval_rate * 100).toFixed(1)}%
              </span>
            </div>

            <div className="glass-panel p-3.5 rounded-xl border border-slate-800">
              <span className="text-xs text-slate-400 block font-medium">Edit Rate</span>
              <span className="text-xl font-bold text-blue-400">
                {(stats.edit_rate * 100).toFixed(1)}%
              </span>
            </div>

            <div className="glass-panel p-3.5 rounded-xl border border-slate-800">
              <span className="text-xs text-slate-400 block font-medium">Reject Rate</span>
              <span className="text-xl font-bold text-rose-400">
                {(stats.reject_rate * 100).toFixed(1)}%
              </span>
            </div>

            <div className="glass-panel p-3.5 rounded-xl border border-slate-800">
              <span className="text-xs text-slate-400 block font-medium">Avg Edit Dist</span>
              <span className="text-xl font-bold text-purple-400">
                {stats.avg_normalized_edit_distance.toFixed(3)}
              </span>
            </div>
          </div>
        )}

        {/* Feedback Alert */}
        {feedbackMsg && (
          <div
            className={`p-4 rounded-xl text-sm flex items-center gap-3 border ${
              feedbackMsg.type === "success"
                ? "bg-emerald-950/40 text-emerald-300 border-emerald-800/50"
                : "bg-rose-950/40 text-rose-300 border-rose-800/50"
            }`}
          >
            {feedbackMsg.type === "success" ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
            ) : (
              <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
            )}
            <span>{feedbackMsg.text}</span>
          </div>
        )}

        {/* Split Layout: Queue List vs Review Workspace */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Pending Items List (5 cols) */}
          <div className="lg:col-span-5 glass-panel rounded-2xl p-4 border border-slate-800 space-y-3">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider px-2">
              Pending Verification Requests ({pending.length})
            </h3>

            {pending.length === 0 ? (
              <div className="text-center py-16 text-slate-500 space-y-2">
                <FileCheck className="w-8 h-8 mx-auto text-slate-600" />
                <p className="text-sm">Queue is empty. No drafts pending review.</p>
              </div>
            ) : (
              <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
                {pending.map((item) => {
                  const isSelected = selectedReview?.thread_id === item.thread_id;
                  return (
                    <div
                      key={item.thread_id}
                      onClick={() => handleSelect(item)}
                      className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                        isSelected
                          ? "bg-slate-900 border-amber-400/80 shadow-md shadow-amber-500/5"
                          : "bg-slate-950/50 hover:bg-slate-900/60 border-slate-800/80"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-[11px] font-mono font-bold text-amber-400">
                          {item.thread_id}
                        </span>
                        <span className="text-[10px] text-slate-500 flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {formatAge(item.age_minutes)}
                        </span>
                      </div>

                      <p className="text-xs text-slate-200 font-medium line-clamp-2 mb-2">
                        {item.query}
                      </p>

                      <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-slate-800/50">
                        <span className="uppercase text-slate-500 font-semibold">{item.route || "UNKNOWN"}</span>
                        <span>{item.financial_year || "2024-25"}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Right Column: Review Workspace (7 cols) */}
          <div className="lg:col-span-7 glass-panel rounded-2xl p-5 sm:p-6 border border-slate-800 flex flex-col justify-between space-y-5">
            {selectedReview ? (
              <div className="space-y-5">
                {/* Query Header */}
                <div className="border-b border-slate-800 pb-4 space-y-1.5">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                      {selectedReview.route}
                    </span>
                    <span className="text-xs text-slate-400">
                      FY: {selectedReview.financial_year || "2024-25"} • {selectedReview.taxpayer_type || "Individual"}
                    </span>
                  </div>
                  <h2 className="text-base font-bold text-slate-100">{selectedReview.query}</h2>
                </div>

                {/* Editable Draft Area */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-slate-300">
                      Draft Legal Answer (Edit as needed):
                    </label>
                    <span className="text-[11px] text-slate-500">Supports Markdown & [C#] Citations</span>
                  </div>
                  <textarea
                    rows={9}
                    value={editedAnswer}
                    onChange={(e) => setEditedAnswer(e.target.value)}
                    className="w-full bg-slate-950 text-slate-100 font-mono text-xs p-3.5 rounded-xl border border-slate-700/80 focus:ring-1 focus:ring-amber-400 focus:outline-none resize-y"
                  />
                </div>

                {/* Reviewer Note */}
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-300">
                    Reviewer Note / Rationale (Optional for approve, recommended for edit/reject):
                  </label>
                  <input
                    type="text"
                    value={reviewerNote}
                    onChange={(e) => setReviewerNote(e.target.value)}
                    placeholder="e.g. Verified deduction limits against Finance Act 2024 amendments"
                    className="w-full bg-slate-950 text-slate-100 text-xs px-3 py-2 rounded-lg border border-slate-700 focus:ring-1 focus:ring-amber-400 focus:outline-none"
                  />
                </div>

                {/* Action Buttons */}
                <div className="pt-3 border-t border-slate-800 flex flex-wrap items-center justify-end gap-3">
                  <button
                    onClick={() => handleDecision("reject")}
                    disabled={isSubmitting}
                    className="px-4 py-2 bg-rose-950/80 hover:bg-rose-900 text-rose-300 border border-rose-800/80 rounded-xl text-xs font-bold transition-colors flex items-center gap-1.5 disabled:opacity-50"
                  >
                    <XCircle className="w-4 h-4 text-rose-400" />
                    <span>Reject (Enforce Refusal)</span>
                  </button>

                  <button
                    onClick={() => handleDecision("edit")}
                    disabled={isSubmitting}
                    className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold transition-colors flex items-center gap-1.5 shadow-lg shadow-blue-500/20 disabled:opacity-50"
                  >
                    <Edit3 className="w-4 h-4" />
                    <span>Save Edit & Approve</span>
                  </button>

                  <button
                    onClick={() => handleDecision("approve")}
                    disabled={isSubmitting}
                    className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold transition-colors flex items-center gap-1.5 shadow-lg shadow-emerald-500/20 disabled:opacity-50"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Approve Draft</span>
                  </button>
                </div>
              </div>
            ) : (
              <div className="text-center py-24 text-slate-500">
                <Inbox className="w-12 h-12 mx-auto text-slate-700 mb-2" />
                <p className="text-sm">Select a pending review from the left column to begin evaluation.</p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
