import { getCostSummary, getReviewHistory, getReviewStats } from "@/lib/api";
import { RepoSelector } from "@/components/RepoSelector";
import { ReviewHistoryTable } from "@/components/ReviewHistoryTable";
import { StatTile } from "@/components/StatTile";

function formatUsd(v: number): string {
  return `$${v.toFixed(2)}`;
}

function formatPercent(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
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
      <main className="mx-auto max-w-5xl px-6 py-10">
        <h1 className="text-xl font-semibold text-ink-primary">AI Code Reviewer Dashboard</h1>
        <p className="mt-2 text-sm text-ink-secondary">
          Enter a repository (owner/repo) to see its review history.
        </p>
        <div className="mt-4">
          <RepoSelector initialRepo="" />
        </div>
      </main>
    );
  }

  let history: Awaited<ReturnType<typeof getReviewHistory>> | undefined;
  let stats: Awaited<ReturnType<typeof getReviewStats>> | undefined;
  let cost: Awaited<ReturnType<typeof getCostSummary>> | undefined;
  let loadError: string | null = null;

  try {
    [history, stats, cost] = await Promise.all([
      getReviewHistory(repo),
      getReviewStats(repo),
      getCostSummary(repo),
    ]);
  } catch (err) {
    loadError = err instanceof Error ? err.message : "Failed to load dashboard data.";
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-ink-primary">AI Code Reviewer Dashboard</h1>
          <p className="mt-1 text-sm text-ink-secondary">{repo}</p>
        </div>
        <RepoSelector initialRepo={repo} />
      </div>

      {loadError || !history || !stats || !cost ? (
        <div className="mt-8 rounded-lg border border-border bg-surface p-8 text-center text-sm text-ink-secondary">
          Could not load data: {loadError ?? "unknown error"}
        </div>
      ) : (
        <>
          <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile label="Reviews" value={String(cost.review_count)} />
            <StatTile
              label="Total cost"
              value={formatUsd(cost.total_cost_usd)}
              sparklineValues={history.reviews.map((r) => r.cost_usd).reverse()}
            />
            <StatTile label="Avg cost / PR" value={formatUsd(cost.avg_cost_per_pr_usd)} />
            <StatTile label="False positive rate" value={formatPercent(stats.false_positive_rate)} />
          </div>

          <h2 className="mt-10 text-sm font-medium text-ink-secondary">Review history</h2>
          <div className="mt-3">
            <ReviewHistoryTable reviews={history.reviews} />
          </div>
        </>
      )}
    </main>
  );
}
