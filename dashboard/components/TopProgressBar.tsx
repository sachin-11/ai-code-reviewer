"use client";

import { useRepoNavigation } from "./RepoNavigation";

export function TopProgressBar() {
  const { isPending } = useRepoNavigation();

  return (
    <div
      className="pointer-events-none fixed top-0 right-0 left-0 z-20 h-0.5 overflow-hidden bg-transparent"
      role="progressbar"
      aria-hidden={!isPending}
    >
      {isPending && <div className="h-full w-full origin-left animate-progress-sweep bg-series-1" />}
    </div>
  );
}
