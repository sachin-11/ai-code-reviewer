"use client";

import type { ReactNode } from "react";
import { useRepoNavigation } from "./RepoNavigation";

export function ContentTransition({ children }: { children: ReactNode }) {
  const { isPending } = useRepoNavigation();

  return (
    <div
      className={`transition-opacity duration-200 ${isPending ? "pointer-events-none opacity-50" : "opacity-100"}`}
      aria-busy={isPending}
    >
      {children}
    </div>
  );
}
