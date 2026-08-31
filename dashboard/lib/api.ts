const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:8000";

export type Severity = "critical" | "high" | "medium" | "low";

export interface Review {
  id: number;
  repo_full_name: string;
  pr_number: number;
  head_sha: string;
  base_sha: string;
  issue_count: number;
  verified_patch_count: number;
  fix_pr_url: string | null;
  summary: string | null;
  cost_usd: number;
  trace_url: string | null;
  latency_seconds: number | null;
  iteration_count: number | null;
  hit_max_iterations: boolean;
  node_latencies: Record<string, number> | null;
  created_at: string;
  severity_breakdown: Partial<Record<Severity, number>>;
}

export interface CostSummary {
  review_count: number;
  total_cost_usd: number;
  avg_cost_per_pr_usd: number;
}

export interface FalsePositiveStats {
  total: number;
  dismissed: number;
  false_positive_rate: number;
}

export interface EvalQualitySummary {
  sample_count: number;
  total_judged: number;
  valid_rate: number | null;
}

export interface LatencySummary {
  review_count: number;
  avg_latency_seconds: number | null;
  max_latency_seconds: number | null;
  avg_iteration_count: number | null;
  max_iteration_count: number | null;
  hit_max_iterations_count: number;
  hit_max_iterations_rate: number | null;
}

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

export function getReviewHistory(repo: string, limit = 20): Promise<{ reviews: Review[] }> {
  return fetchJson(`/api/reviews?repo=${encodeURIComponent(repo)}&limit=${limit}`);
}

export function getReviewStats(repo: string): Promise<FalsePositiveStats> {
  return fetchJson(`/api/reviews/stats?repo=${encodeURIComponent(repo)}`);
}

export function getCostSummary(repo: string): Promise<CostSummary> {
  return fetchJson(`/api/reviews/cost?repo=${encodeURIComponent(repo)}`);
}

export function getKnownRepos(): Promise<{ repos: string[] }> {
  return fetchJson(`/api/reviews/repos`);
}

export function getEvalSummary(repo: string): Promise<EvalQualitySummary> {
  return fetchJson(`/api/reviews/eval?repo=${encodeURIComponent(repo)}`);
}

export function getLatencySummary(repo: string): Promise<LatencySummary> {
  return fetchJson(`/api/reviews/latency?repo=${encodeURIComponent(repo)}`);
}
