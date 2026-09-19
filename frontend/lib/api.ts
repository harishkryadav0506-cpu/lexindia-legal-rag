/**
 * frontend/lib/api.ts — API Client for LexIndia FastAPI backend.
 */

import {
  QueryRequest,
  QueryResponse,
  ReviewDecisionRequest,
  ReviewPendingItem,
  ReviewStatsResponse,
  GraphResponse,
} from "@/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://localhost:8000";

export async function sendQuery(payload: QueryRequest): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE_URL}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Query failed [${res.status}]: ${errorText}`);
  }

  return res.json();
}

export async function fetchPendingReviews(): Promise<ReviewPendingItem[]> {
  const res = await fetch(`${API_BASE_URL}/reviews/pending`, {
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`Failed to fetch pending reviews: ${res.statusText}`);
  }

  return res.json();
}

export async function submitReviewDecision(
  threadId: string,
  payload: ReviewDecisionRequest
): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE_URL}/reviews/${threadId}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Decision submission failed [${res.status}]: ${errorText}`);
  }

  return res.json();
}

export async function fetchReviewStats(): Promise<ReviewStatsResponse> {
  const res = await fetch(`${API_BASE_URL}/reviews/stats`, {
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`Failed to fetch review stats: ${res.statusText}`);
  }

  return res.json();
}

export async function fetchCitationGraph(
  sectionId: string,
  hops: number = 2
): Promise<GraphResponse> {
  const params = new URLSearchParams({
    section_id: sectionId,
    hops: hops.toString(),
  });

  const res = await fetch(`${API_BASE_URL}/graph?${params.toString()}`);

  if (!res.ok) {
    throw new Error(`Failed to fetch citation graph: ${res.statusText}`);
  }

  return res.json();
}

export async function fetchHealth(): Promise<Record<string, any>> {
  const res = await fetch(`${API_BASE_URL}/health`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.status}`);
  }
  return res.json();
}
