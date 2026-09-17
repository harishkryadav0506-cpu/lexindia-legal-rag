/**
 * frontend/types/index.ts — Shared TypeScript interfaces for LexIndia Frontend.
 */

export interface CitationItem {
  citation_id?: string;
  chunk_id: string;
  section_id: string;
  doc_type: string;
  authority_level?: number;
  source_url: string;
  page_number: number;
  score: number;
  graph_expanded?: boolean;
  text?: string;
}

export interface AgentTraceItem {
  agent: string;
  action: string;
  latency_ms: number;
  inputs_summary: string;
  outputs_summary: string;
}

export interface QueryRequest {
  question: string;
  financial_year?: string;
  taxpayer_type?: string;
  require_review?: boolean;
  mock_429?: boolean;
}

export interface QueryResponse {
  status: "complete" | "awaiting_review";
  thread_id?: string;
  answer?: string;
  draft_answer?: string;
  final_answer?: string;
  citations: CitationItem[];
  confidence: number;
  refused: boolean;
  route: string;
  latency_ms: number;
  fallback_used: boolean;
  fallback_model?: string | null;
  agent_trace: AgentTraceItem[];
  review_required?: boolean;
}

export interface ReviewDecisionRequest {
  action: "approve" | "edit" | "reject";
  edited_answer?: string;
  reviewer_note?: string;
}

export interface ReviewPendingItem {
  id?: number;
  thread_id: string;
  query: string;
  financial_year?: string;
  taxpayer_type?: string;
  draft_answer: string;
  citations: CitationItem[];
  route?: string;
  confidence?: number;
  age_minutes: number;
  created_at?: string;
}

export interface ReviewStatsResponse {
  approval_rate: number;
  edit_rate: number;
  reject_rate: number;
  avg_normalized_edit_distance: number;
  review_trigger_rate: number;
  total_reviews: number;
  total_decided: number;
  pending_count: number;
}

export interface GraphNode {
  id: string;
  label: string;
  authority_level: number;
  doc_type: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  relation: string;
  source_doc?: string;
}

export interface GraphResponse {
  section_id: string;
  hops: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
}
