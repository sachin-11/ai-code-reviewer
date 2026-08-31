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
    <select
      value={initialRepo}
      onChange={handleChange}
      className="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-ink-primary focus:outline-none focus:ring-1 focus:ring-series-1"
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
  );
}
