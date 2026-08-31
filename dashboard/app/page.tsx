import { getCostSummary, getKnownRepos, getReviewHistory, getReviewStats } from "@/lib/api";
import { RepoSelector } from "@/components/RepoSelector";
import { ReviewHistoryTable } from "@/components/ReviewHistoryTable";
import { StatTile } from "@/components/StatTile";
import { AvgIcon, CostIcon, FalsePositiveIcon, ReviewsIcon } from "@/components/icons";

function formatUsd(v: number): string {
  return `$${v.toFixed(2)}`;
}

function formatPercent(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

function Header({ repos, repo }: { repos: string[]; repo: string }) {
  return (
    <header className="border-b border-grid bg-surface">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 px-6 py-5">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-series-1 text-white">
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M9 11l3 3L22 4" />
              <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
            </svg>
          </div>
          <div>
            <h1 className="text-base font-semibold text-ink-primary">AI Code Reviewer</h1>
            {repo && <p className="text-xs text-ink-muted">{repo}</p>}
          </div>
        </div>
        <RepoSelector repos={repos} initialRepo={repo} />
      </div>
    </header>
  );
}

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ repo?: string }>;
}) {
  const resolvedSearchParams = await searchParams;
  const repo = resolvedSearchParams.repo?.trim() ?? "";

  let repos: string[] = [];
  try {
    repos = (await getKnownRepos()).repos;
  } catch {
    repos = [];
  }

  if (!repo) {
    return (
      <>
        <Header repos={repos} repo="" />
        <main className="mx-auto max-w-5xl px-6 py-16 text-center">
          <p className="text-sm text-ink-secondary">
            {repos.length > 0
              ? "Pick a repository above to see its review history."
              : "No repositories have been reviewed yet."}
          </p>
        </main>
      </>
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
    <>
      <Header repos={repos} repo={repo} />
      <main className="mx-auto max-w-5xl px-6 py-8">
        {loadError || !history || !stats || !cost ? (
          <div className="rounded-xl border border-border bg-surface p-10 text-center">
            <p className="text-sm font-medium text-status-critical">Could not load dashboard data</p>
            <p className="mt-1 text-xs text-ink-muted">{loadError ?? "Unknown error"}</p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatTile label="Reviews" value={String(cost.review_count)} icon={<ReviewsIcon />} />
              <StatTile
                label="Total cost"
                value={formatUsd(cost.total_cost_usd)}
                icon={<CostIcon />}
                sparklineValues={history.reviews.map((r) => r.cost_usd).reverse()}
              />
              <StatTile label="Avg cost / PR" value={formatUsd(cost.avg_cost_per_pr_usd)} icon={<AvgIcon />} />
              <StatTile
                label="False positive rate"
                value={formatPercent(stats.false_positive_rate)}
                icon={<FalsePositiveIcon />}
              />
            </div>

            <div className="mt-10 flex items-baseline justify-between">
              <h2 className="text-sm font-semibold text-ink-primary">Review history</h2>
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
    </>
  );
}
