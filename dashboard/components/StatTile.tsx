import type { ReactNode } from "react";
import { Sparkline } from "./Sparkline";

export type StatTone = "good" | "warning" | "critical" | "neutral";

interface StatTileProps {
  label: string;
  value: string;
  icon?: ReactNode;
  sparklineValues?: number[];
  tone?: StatTone;
  hint?: string;
}

const TONE_TEXT: Record<StatTone, string> = {
  good: "text-status-good",
  warning: "text-status-warning",
  critical: "text-status-critical",
  neutral: "text-ink-primary",
};

export function StatTile({ label, value, icon, sparklineValues, tone = "neutral", hint }: StatTileProps) {
  return (
    <div className="group rounded-xl border border-border bg-surface p-4 shadow-card transition-all hover:-translate-y-0.5 hover:border-ink-muted/40 hover:shadow-lifted">
      <div className="flex items-center gap-2 text-ink-muted">
        {icon}
        <span className="text-xs font-medium uppercase tracking-wide">{label}</span>
      </div>
      <div className={`font-mono-data tabular mt-2 text-[1.65rem] leading-none font-semibold ${TONE_TEXT[tone]}`}>
        {value}
      </div>
      {hint && <p className="mt-1.5 text-xs text-ink-muted">{hint}</p>}
      {sparklineValues && sparklineValues.length > 1 && (
        <Sparkline values={sparklineValues} className="mt-3" />
      )}
    </div>
  );
}
