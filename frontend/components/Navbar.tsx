"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Scale, AlertTriangle, Layers, Inbox } from "lucide-react";
import { fetchHealth, fetchReviewStats } from "@/lib/api";

export default function Navbar() {
  const pathname = usePathname();
  const [esConnected, setEsConnected] = useState<boolean | null>(null);
  const [pendingCount, setPendingCount] = useState<number>(0);

  const refreshStats = () => {
    fetchReviewStats()
      .then((data) => {
        setPendingCount(data.pending_count || 0);
      })
      .catch(() => {});
  };

  useEffect(() => {
    fetchHealth()
      .then((data) => {
        setEsConnected(data?.components?.elasticsearch?.status === "connected");
      })
      .catch(() => setEsConnected(false));

    refreshStats();

    // P13 / FIX 12: Refetch pending count on route focus and query completed events
    if (typeof window !== "undefined") {
      window.addEventListener("focus", refreshStats);
      window.addEventListener("lexindia:query_completed", refreshStats);
      return () => {
        window.removeEventListener("focus", refreshStats);
        window.removeEventListener("lexindia:query_completed", refreshStats);
      };
    }
  }, [pathname]);

  return (
    <header className="sticky top-0 z-40 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Logo and Brand */}
        <Link href="/" className="flex items-center gap-3 group">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-amber-600 to-amber-400 p-0.5 shadow-lg shadow-amber-500/20 group-hover:scale-105 transition-transform">
            <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
              <Scale className="w-5 h-5 text-amber-400" />
            </div>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-lg text-slate-100 tracking-tight">LexIndia</span>
              <span className="text-[10px] font-semibold bg-amber-500/10 text-amber-400 px-1.5 py-0.5 rounded border border-amber-500/20">
                PROD RAG
              </span>
            </div>
            <p className="text-xs text-slate-400 hidden sm:block">Legal RAG System for Indian Tax Law</p>
          </div>
        </Link>

        {/* Navigation Tabs */}
        <nav className="flex items-center gap-1 sm:gap-2">
          <Link
            href="/"
            className={`px-3.5 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 ${
              pathname === "/"
                ? "bg-slate-800 text-amber-400 border border-slate-700"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
            }`}
          >
            <Layers className="w-4 h-4" />
            <span>Research</span>
          </Link>

          <Link
            href="/review"
            className={`px-3.5 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 relative ${
              pathname === "/review"
                ? "bg-slate-800 text-amber-400 border border-slate-700"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
            }`}
          >
            <Inbox className="w-4 h-4" />
            <span>Review Queue</span>
            {pendingCount > 0 && (
              <span className="inline-flex items-center justify-center px-1.5 py-0.5 text-xs font-bold leading-none text-slate-950 bg-amber-400 rounded-full">
                {pendingCount}
              </span>
            )}
          </Link>
        </nav>

        {/* System Health Badge */}
        <div className="flex items-center gap-3">
          <div
            className={`hidden md:flex items-center gap-2 text-xs px-2.5 py-1 rounded-full border ${
              esConnected
                ? "bg-emerald-950/40 text-emerald-400 border-emerald-800/40"
                : esConnected === false
                ? "bg-rose-950/40 text-rose-400 border-rose-800/40"
                : "bg-slate-900 text-slate-400 border-slate-800"
            }`}
          >
            {esConnected ? (
              <>
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span>ES 8.13 Connected</span>
              </>
            ) : esConnected === false ? (
              <>
                <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
                <span>ES Offline</span>
              </>
            ) : (
              <span>Checking...</span>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
