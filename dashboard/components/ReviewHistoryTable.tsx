import type { Review } from "@/lib/api";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatCost(v: number): string {
  return `$${v.toFixed(4)}`;
}

export function ReviewHistoryTable({ reviews }: { reviews: Review[] }) {
  if (reviews.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-surface p-8 text-center text-sm text-ink-secondary">
        No reviews recorded yet for this repository.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-surface">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-grid text-ink-muted">
            <th className="px-4 py-2 font-medium">PR</th>
            <th className="px-4 py-2 font-medium">Date</th>
            <th className="px-4 py-2 text-right font-medium">Issues</th>
            <th className="px-4 py-2 text-right font-medium">Verified fixes</th>
            <th className="px-4 py-2 text-right font-medium">Cost</th>
            <th className="px-4 py-2 font-medium">Fix PR</th>
            <th className="px-4 py-2 font-medium">Trace</th>
          </tr>
        </thead>
        <tbody>
          {reviews.map((review) => (
            <tr key={review.id} className="border-b border-grid last:border-0">
              <td className="px-4 py-2 text-ink-primary">#{review.pr_number}</td>
              <td className="px-4 py-2 text-ink-secondary">{formatDate(review.created_at)}</td>
              <td className="tabular px-4 py-2 text-right text-ink-primary">{review.issue_count}</td>
              <td className="tabular px-4 py-2 text-right text-ink-primary">
                {review.verified_patch_count}
              </td>
              <td className="tabular px-4 py-2 text-right text-ink-primary">
                {formatCost(review.cost_usd)}
              </td>
              <td className="px-4 py-2">
                {review.fix_pr_url ? (
                  <a
                    href={review.fix_pr_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-series-1 underline underline-offset-2"
                  >
                    View
                  </a>
                ) : (
                  <span className="text-ink-muted">—</span>
                )}
              </td>
              <td className="px-4 py-2">
                {review.trace_url ? (
                  <a
                    href={review.trace_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-series-1 underline underline-offset-2"
                  >
                    View
                  </a>
                ) : (
                  <span className="text-ink-muted">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
