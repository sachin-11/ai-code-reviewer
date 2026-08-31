import type { Review } from "@/lib/api";
import { EmptyStateIcon, ExternalLinkIcon } from "./icons";
import { SeverityBadges } from "./SeverityBadges";

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

function LinkPill({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs font-medium text-ink-secondary transition-colors hover:border-series-1 hover:text-series-1"
    >
      {label}
      <ExternalLinkIcon />
    </a>
  );
}

export function ReviewHistoryTable({ reviews }: { reviews: Review[] }) {
  if (reviews.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-border bg-surface p-12 text-center">
        <EmptyStateIcon className="text-ink-muted" />
        <p className="text-sm text-ink-secondary">No reviews recorded yet for this repository.</p>
        <p className="text-xs text-ink-muted">
          Open or update a pull request to trigger the first automated review.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-surface">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-grid text-ink-muted">
            <th className="px-4 py-3 text-xs font-medium uppercase tracking-wide">PR</th>
            <th className="px-4 py-3 text-xs font-medium uppercase tracking-wide">Date</th>
            <th className="px-4 py-3 text-xs font-medium uppercase tracking-wide">Issues found</th>
            <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wide">
              Verified fixes
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wide">Cost</th>
            <th className="px-4 py-3 text-xs font-medium uppercase tracking-wide">Links</th>
          </tr>
        </thead>
        <tbody>
          {reviews.map((review) => (
            <tr
              key={review.id}
              className="border-b border-grid last:border-0 hover:bg-plane/60"
            >
              <td className="px-4 py-3 font-medium text-ink-primary">#{review.pr_number}</td>
              <td className="px-4 py-3 whitespace-nowrap text-ink-secondary">
                {formatDate(review.created_at)}
              </td>
              <td className="px-4 py-3">
                <SeverityBadges breakdown={review.severity_breakdown} />
              </td>
              <td className="tabular px-4 py-3 text-right text-ink-primary">
                {review.verified_patch_count > 0 ? (
                  <span className="text-status-good">{review.verified_patch_count}</span>
                ) : (
                  <span className="text-ink-muted">0</span>
                )}
              </td>
              <td className="tabular px-4 py-3 text-right text-ink-primary">
                {formatCost(review.cost_usd)}
              </td>
              <td className="px-4 py-3">
                <div className="flex flex-wrap gap-1.5">
                  {review.fix_pr_url && <LinkPill href={review.fix_pr_url} label="Fix PR" />}
                  {review.trace_url && <LinkPill href={review.trace_url} label="Trace" />}
                  {!review.fix_pr_url && !review.trace_url && (
                    <span className="text-ink-muted">—</span>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
