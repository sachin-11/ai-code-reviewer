import type { ReactNode } from "react";
import { Sparkline } from "./Sparkline";

interface StatTileProps {
  label: string;
  value: string;
  icon?: ReactNode;
  sparklineValues?: number[];
}

export function StatTile({ label, value, icon, sparklineValues }: StatTileProps) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4 transition-colors hover:border-ink-muted/40">
      <div className="flex items-center gap-2 text-ink-muted">
        {icon}
        <span className="text-xs font-medium uppercase tracking-wide">{label}</span>
      </div>
      <div className="tabular mt-2 text-[1.75rem] leading-none font-semibold text-ink-primary">
        {value}
      </div>
      {sparklineValues && sparklineValues.length > 1 && (
        <Sparkline values={sparklineValues} className="mt-3" />
      )}
    </div>
  );
}
