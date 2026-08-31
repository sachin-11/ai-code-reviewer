import type { Severity } from "@/lib/api";

const SEVERITY_ORDER: Severity[] = ["critical", "high", "medium", "low"];

const SEVERITY_STYLE: Record<Severity, { dot: string; label: string }> = {
  critical: { dot: "bg-status-critical", label: "Critical" },
  high: { dot: "bg-status-serious", label: "High" },
  medium: { dot: "bg-status-warning", label: "Medium" },
  low: { dot: "bg-status-good", label: "Low" },
};

export function SeverityBadges({ breakdown }: { breakdown: Partial<Record<Severity, number>> }) {
  const entries = SEVERITY_ORDER.filter((severity) => (breakdown[severity] ?? 0) > 0);

  if (entries.length === 0) {
    return <span className="text-ink-muted">—</span>;
  }

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      {entries.map((severity) => {
        const style = SEVERITY_STYLE[severity];
        return (
          <span key={severity} className="inline-flex items-center gap-1.5 text-xs text-ink-secondary">
            <span className={`h-2 w-2 shrink-0 rounded-full ${style.dot}`} aria-hidden="true" />
            <span className="tabular font-medium text-ink-primary">{breakdown[severity]}</span>
            <span>{style.label}</span>
          </span>
        );
      })}
    </div>
  );
}
