import { Sparkline } from "./Sparkline";

interface StatTileProps {
  label: string;
  value: string;
  sparklineValues?: number[];
}

export function StatTile({ label, value, sparklineValues }: StatTileProps) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="text-sm text-ink-secondary">{label}</div>
      <div className="tabular mt-1 text-2xl font-semibold text-ink-primary">{value}</div>
      {sparklineValues && sparklineValues.length > 1 && (
        <Sparkline values={sparklineValues} className="mt-3" />
      )}
    </div>
  );
}
