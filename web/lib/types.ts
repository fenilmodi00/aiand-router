export type Range = "24h" | "7d" | "30d" | "all";

export type Candidate = {
  id: string;
  display_name: string;
  enabled: boolean;
};

export type CandidateMix = {
  id: string;
  display_name: string;
  count: number;
  pct: number;
};

export type UsageBucket = {
  ts: string;
  requests: number;
  by_model: Record<string, number>;
  spend_usd?: number;
  baseline_usd?: number;
};

export type Overview = {
  range: string;
  virtual_model: string;
  routed_requests: number;
  spend_usd: number;
  budget_usd: number;
  savings_usd: number;
  savings_pct: number;
  fallback_count: number;
  fallback_rate: number;
  cache_hits: number;
  aiand_key_set: boolean;
  candidates: Candidate[];
  candidate_mix: CandidateMix[];
  usage_buckets: UsageBucket[];
  cost_routed_usd: number;
  cost_baseline_usd: number;
};

export type Inference = {
  ts: string | null;
  selected: string | null;
  phase: string | null;
  tokens_in: number;
  tokens_out: number;
  latency_ms: number;
  status: number;
  cache_hit: boolean;
  path: string;
  cost_usd: number;
  ttft_ms: number | null;
  llmaj_score: number | null;
  tests_passed: boolean | null;
};

export type Inferences = {
  data: Inference[];
};

export type CatalogModel = {
  id: string;
  object?: string;
  owned_by?: string;
  enabled?: boolean;
  aa_index?: number | null;
  aa_source?: string;
  description?: string;
  display_name?: string;
  input_per_1m?: number;
  output_per_1m?: number;
};

export type ModelsResponse = {
  object: string;
  data: CatalogModel[];
};

export type Health = {
  ok: boolean;
  spend_usd: number;
  budget_usd: number;
  aiand_key_set: boolean;
};

export type FetchResult<T> = {
  ok: boolean;
  status: number;
  data: T | null;
  error: string | null;
};

export type MaskedKey = {
  set: boolean;
  masked: string;
  hidden: string;
};

export const EMPTY_OVERVIEW: Overview = {
  range: "30d",
  virtual_model: "router/auto",
  routed_requests: 0,
  spend_usd: 0,
  budget_usd: 0,
  savings_usd: 0,
  savings_pct: 0,
  fallback_count: 0,
  fallback_rate: 0,
  cache_hits: 0,
  aiand_key_set: false,
  candidates: [],
  candidate_mix: [],
  usage_buckets: [],
  cost_routed_usd: 0,
  cost_baseline_usd: 0,
};

export const EMPTY_HEALTH: Health = {
  ok: false,
  spend_usd: 0,
  budget_usd: 0,
  aiand_key_set: false,
};

export const MIX_COLORS = [
  "#3b82f6",
  "#f97316",
  "#facc15",
  "#c8a06a",
  "#10b981",
  "#2dd4bf",
  "#ec4899",
  "#a3be8c",
  "#f2613c",
];
