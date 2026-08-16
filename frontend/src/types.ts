export type KnowledgeStatus =
  | "pending"
  | "confirmed"
  | "partially_confirmed"
  | "contested"
  | "unverified"
  | "rejected";

export interface Topic {
  id: string;
  title: string;
  question: string;
  keywords: string[];
  enabled_source_ids: string[];
  schedule_hour: number;
  timezone: string;
  is_active: boolean;
  next_run_at: string | null;
  created_at: string;
}

export interface ResearchRun {
  id: string;
  topic_id: string;
  draft_id: string | null;
  kind: "research" | "verify";
  trigger: string;
  status: "queued" | "running" | "completed" | "failed" | "paused_quota";
  progress_stage: string;
  error_message: string | null;
  documents_processed: number;
  model_requests: number;
  created_at: string;
}

export interface ResearchDraft {
  id: string;
  topic_id: string;
  report_text: string;
  status: KnowledgeStatus;
  searched_domains: string[];
  cited_urls: string[];
  model_name: string;
  created_at: string;
}

export interface CandidateInsight {
  id: string;
  title: string;
  explanation: string;
  supporting_claim_ids: string[];
  conflicting_claim_ids: string[];
  confidence: "low" | "medium" | "high";
  verification_status: KnowledgeStatus;
  review_status: "draft" | "useful" | "rejected";
}

export interface GraphNodeRecord {
  id: string;
  kind: "claim" | "concept" | "hypothesis";
  label: string;
  status: string;
  details: Record<string, unknown>;
}

export interface GraphEdgeRecord {
  id: string;
  source: string;
  target: string;
  relationship: string;
  status: string;
}

export interface GraphData {
  nodes: GraphNodeRecord[];
  edges: GraphEdgeRecord[];
}

export interface SourceCatalogEntry {
  id: string;
  publisher: string;
  hostname: string;
  allowed_paths: string[];
  category: string;
  topic_tags: string[];
  evidence_role: "primary" | "secondary" | "discovery_only";
  access_mode: "full_text" | "abstract_only" | "metadata_only" | "discovery_only";
  approval_reason: string;
  reviewed_at: string;
  is_enabled: boolean;
  is_builtin: boolean;
}
