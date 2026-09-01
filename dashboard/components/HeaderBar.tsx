"use client";

import { useSearchParams } from "next/navigation";
import { RepoSelector } from "./RepoSelector";

export function HeaderBar({ repos }: { repos: string[] }) {
  const searchParams = useSearchParams();
  const repo = searchParams.get("repo")?.trim() ?? "";

  return (
    <header className="sticky top-0 z-10 border-b border-grid bg-surface/90 backdrop-blur-sm">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-series-1 text-white shadow-sm">
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
            <h1 className="font-display text-[0.95rem] leading-tight font-bold tracking-tight text-ink-primary">
              AI Code Reviewer
            </h1>
            <p className="text-xs text-ink-muted">{repo || "Automated pull request review"}</p>
          </div>
        </div>
        <RepoSelector repos={repos} initialRepo={repo} />
      </div>
    </header>
  );
}
