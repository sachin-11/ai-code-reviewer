"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

export function RepoSelector({ initialRepo }: { initialRepo: string }) {
  const router = useRouter();
  const [value, setValue] = useState(initialRepo);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) return;
    router.push(`/?repo=${encodeURIComponent(trimmed)}`);
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="owner/repo"
        className="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-ink-primary placeholder:text-ink-muted focus:outline-none focus:ring-1 focus:ring-series-1"
      />
      <button type="submit" className="rounded-md bg-series-1 px-3 py-1.5 text-sm font-medium text-white">
        View
      </button>
    </form>
  );
}
