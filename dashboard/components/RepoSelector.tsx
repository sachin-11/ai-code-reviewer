"use client";

import { useRouter } from "next/navigation";
import type { ChangeEvent } from "react";

export function RepoSelector({ repos, initialRepo }: { repos: string[]; initialRepo: string }) {
  const router = useRouter();

  function handleChange(e: ChangeEvent<HTMLSelectElement>) {
    const repo = e.target.value;
    if (repo) {
      router.push(`/?repo=${encodeURIComponent(repo)}`);
    }
  }

  if (repos.length === 0) {
    return <p className="text-sm text-ink-muted">No reviewed repositories yet.</p>;
  }

  return (
    <div className="relative">
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-ink-muted"
        aria-hidden="true"
      >
        <path d="M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6z" />
      </svg>
      <select
        value={initialRepo}
        onChange={handleChange}
        className="appearance-none rounded-md border border-border bg-surface py-1.5 pr-8 pl-9 text-sm text-ink-primary focus:outline-none focus:ring-1 focus:ring-series-1"
      >
        <option value="" disabled>
          Select a repository
        </option>
        {repos.map((repo) => (
          <option key={repo} value={repo}>
            {repo}
          </option>
        ))}
      </select>
      <svg
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-ink-muted"
        aria-hidden="true"
      >
        <path d="M6 9l6 6 6-6" />
      </svg>
    </div>
  );
}
