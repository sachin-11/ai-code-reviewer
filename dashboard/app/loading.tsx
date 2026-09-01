// Suspense fallback for this route segment -- fires on a cold/hard load
// (typing the URL, a refresh, an external link) while page.tsx's data
// fetch is in flight. It does NOT fire for the repo switcher's own
// searchParams-only client navigation (verified live); that case is
// handled instead by RepoNavigation's useTransition + TopProgressBar /
// ContentTransition, which reliably covers it.
function TileSkeleton() {
  return (
    <div className="rounded-xl border border-border bg-surface p-4 shadow-card">
      <div className="h-3 w-20 animate-pulse rounded bg-grid" />
      <div className="mt-3 h-7 w-16 animate-pulse rounded bg-grid" />
    </div>
  );
}

function SectionSkeleton({ label, tiles }: { label: string; tiles: number }) {
  return (
    <section className="mt-8 first:mt-0">
      <h2 className="font-display text-[0.7rem] font-bold tracking-[0.14em] text-ink-muted uppercase">
        {label}
      </h2>
      <div
        className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-3"
        style={tiles === 2 ? { gridTemplateColumns: "repeat(2, minmax(0, 1fr))" } : undefined}
      >
        {Array.from({ length: tiles }).map((_, i) => (
          <TileSkeleton key={i} />
        ))}
      </div>
    </section>
  );
}

export default function Loading() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-8" aria-busy="true" aria-label="Loading dashboard">
      <SectionSkeleton label="Activity" tiles={3} />
      <SectionSkeleton label="Quality" tiles={2} />
      <SectionSkeleton label="Performance" tiles={3} />

      <div className="mt-10 h-4 w-32 animate-pulse rounded bg-grid" />
      <div className="mt-3 overflow-hidden rounded-xl border border-border bg-surface shadow-card">
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            className="flex items-center gap-6 border-b border-grid px-4 py-3.5 last:border-0"
          >
            <div className="h-3 w-10 animate-pulse rounded bg-grid" />
            <div className="h-3 w-16 animate-pulse rounded bg-grid" />
            <div className="h-3 w-24 animate-pulse rounded bg-grid" />
            <div className="ml-auto h-3 w-14 animate-pulse rounded bg-grid" />
          </div>
        ))}
      </div>
    </main>
  );
}
