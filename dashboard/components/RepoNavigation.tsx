"use client";

import { useRouter } from "next/navigation";
import { createContext, useContext, useTransition, type ReactNode } from "react";

interface RepoNavigationValue {
  isPending: boolean;
  navigate: (repo: string) => void;
}

const RepoNavigationContext = createContext<RepoNavigationValue>({
  isPending: false,
  navigate: () => {},
});

export function RepoNavigationProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  function navigate(repo: string) {
    startTransition(() => {
      router.push(`/?repo=${encodeURIComponent(repo)}`);
    });
  }

  return (
    <RepoNavigationContext.Provider value={{ isPending, navigate }}>
      {children}
    </RepoNavigationContext.Provider>
  );
}

export function useRepoNavigation(): RepoNavigationValue {
  return useContext(RepoNavigationContext);
}
