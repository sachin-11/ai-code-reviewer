import {
  getCostSummary,
  getEvalSummary,
  getLatencySummary,
  getReviewHistory,
  getReviewStats,
} from "@/lib/api";
import { ReviewHistoryTable } from "@/components/ReviewHistoryTable";
import { StatTile, type StatTone } from "@/components/StatTile";
import {
  AvgIcon,
  CostIcon,
  EvalQualityIcon,
  FalsePositiveIcon,
  LatencyIcon,
  LoopLimitIcon,
  ReviewsIcon,
} from "@/components/icons";

function formatUsd(v: number): string {
  return `$${v.toFixed(2)}`;
}

function formatPercent(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

function formatSeconds(v: number | null): string {
  if (v === null) return "—";
  return v < 60 ? `${v.toFixed(1)}s` : `${(v / 60).toFixed(1)}m`;
}

function formatEvalQuality(evalSummary: { sample_count: number; valid_rate: number | null }): string {
  if (evalSummary.sample_count === 0 || evalSummary.valid_rate === null) {
    return "—";
  }
  return formatPercent(evalSummary.valid_rate);
}

// Lower is better: a review getting dismissed a lot is the one signal on
// this dashboard that means the bot itself needs attention, not the code.
function falsePositiveTone(rate: number): StatTone {
  if (rate < 0.1) return "good";
  if (rate < 0.25) return "warning";
  return "critical";
}

// Higher is better: this is the LLM-judge's read on whether findings are
// actually valid, sampled from real production reviews.
function evalQualityTone(sampleCount: number, validRate: number | null): StatTone {
  if (sampleCount === 0 || validRate === null) return "neutral";
  if (validRate >= 0.85) return "good";
  if (validRate >= 0.7) return "warning";
  return "critical";
}

// Any review hitting the loop limit means analyze gave up without a clean
// answer -- rare should stay rare.
function loopLimitTone(reviewCount: number, hitCount: number): StatTone {
  if (reviewCount === 0) return "neutral";
  if (hitCount === 0) return "good";
  const rate = hitCount / reviewCount;
  return rate > 0.1 ? "critical" : "warning";
}

function SectionLabel({ children }: { children: string }) {
  return (
    <h2 className="font-display text-[0.7rem] font-bold tracking-[0.14em] text-ink-muted uppercase">
      {children}
    </h2>
  );
}

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ repo?: string }>;
}) {
  const resolvedSearchParams = await searchParams;
  const repo = resolvedSearchParams.repo?.trim() ?? "";

  if (!repo) {
    return (
      <main className="mx-auto max-w-5xl px-6 py-16 text-center">
        <p className="text-sm text-ink-secondary">
          Pick a repository above to see its review history.
        </p>
      </main>
    );
  }

  let history: Awaited<ReturnType<typeof getReviewHistory>> | undefined;
  let stats: Awaited<ReturnType<typeof getReviewStats>> | undefined;
  let cost: Awaited<ReturnType<typeof getCostSummary>> | undefined;
  let evalSummary: Awaited<ReturnType<typeof getEvalSummary>> | undefined;
  let latency: Awaited<ReturnType<typeof getLatencySummary>> | undefined;
  let loadError: string | null = null;

  try {
    [history, stats, cost, evalSummary, latency] = await Promise.all([
      getReviewHistory(repo),
      getReviewStats(repo),
      getCostSummary(repo),
      getEvalSummary(repo),
      getLatencySummary(repo),
    ]);
  } catch (err) {
    loadError = err instanceof Error ? err.message : "Failed to load dashboard data.";
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-8">
      {loadError || !history || !stats || !cost || !evalSummary || !latency ? (
        <div className="rounded-xl border border-border bg-surface p-10 text-center shadow-card">
          <p className="text-sm font-medium text-status-critical">Could not load dashboard data</p>
          <p className="mt-1 text-xs text-ink-muted">{loadError ?? "Unknown error"}</p>
        </div>
      ) : (
        <>
          <section>
            <SectionLabel>Activity</SectionLabel>
            <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-3">
              <StatTile label="Reviews" value={String(cost.review_count)} icon={<ReviewsIcon />} />
              <StatTile
                label="Total cost"
                value={formatUsd(cost.total_cost_usd)}
                icon={<CostIcon />}
                sparklineValues={history.reviews.map((r) => r.cost_usd).reverse()}
              />
              <StatTile
                label="Avg cost / PR"
                value={formatUsd(cost.avg_cost_per_pr_usd)}
                icon={<AvgIcon />}
              />
            </div>
          </section>

          <section className="mt-8">
            <SectionLabel>Quality</SectionLabel>
            <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <StatTile
                label="False positive rate"
                value={formatPercent(stats.false_positive_rate)}
                icon={<FalsePositiveIcon />}
                tone={falsePositiveTone(stats.false_positive_rate)}
                hint={`${stats.dismissed} of ${stats.total} findings dismissed`}
              />
              <StatTile
                label="Eval quality"
                value={formatEvalQuality(evalSummary)}
                icon={<EvalQualityIcon />}
                tone={evalQualityTone(evalSummary.sample_count, evalSummary.valid_rate)}
                hint={
                  evalSummary.sample_count > 0
                    ? `LLM-judged, ${evalSummary.sample_count} sample(s)`
                    : "No samples judged yet"
                }
              />
            </div>
          </section>

          <section className="mt-8">
            <SectionLabel>Performance</SectionLabel>
            <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-3">
              <StatTile
                label="Avg latency"
                value={formatSeconds(latency.avg_latency_seconds)}
                icon={<LatencyIcon />}
                sparklineValues={history.reviews
                  .map((r) => r.latency_seconds)
                  .filter((v): v is number => v !== null)
                  .reverse()}
              />
              <StatTile
                label="Avg iterations"
                value={latency.avg_iteration_count === null ? "—" : latency.avg_iteration_count.toFixed(1)}
                icon={<AvgIcon />}
              />
              <StatTile
                label="Hit loop limit"
                value={
                  latency.review_count === 0
                    ? "—"
                    : `${latency.hit_max_iterations_count} (${formatPercent(latency.hit_max_iterations_rate ?? 0)})`
                }
                icon={<LoopLimitIcon />}
                tone={loopLimitTone(latency.review_count, latency.hit_max_iterations_count)}
              />
            </div>
          </section>

          <div className="mt-10 flex items-baseline justify-between">
            <h2 className="font-display text-sm font-bold text-ink-primary">Review history</h2>
            <span className="text-xs text-ink-muted">
              {history.reviews.length} review{history.reviews.length === 1 ? "" : "s"}
            </span>
          </div>
          <div className="mt-3">
            <ReviewHistoryTable reviews={history.reviews} />
          </div>
        </>
      )}
    </main>
  );
}
