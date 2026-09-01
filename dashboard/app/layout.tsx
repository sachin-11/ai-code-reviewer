import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Suspense } from "react";
import { ContentTransition } from "@/components/ContentTransition";
import { HeaderBar } from "@/components/HeaderBar";
import { RepoNavigationProvider } from "@/components/RepoNavigation";
import { TopProgressBar } from "@/components/TopProgressBar";
import { getKnownRepos } from "@/lib/api";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Code Reviewer Dashboard",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  let repos: string[] = [];
  try {
    repos = (await getKnownRepos()).repos;
  } catch {
    repos = [];
  }

  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Manrope:wght@500;600;700;800&family=IBM+Plex+Mono:wght@500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <RepoNavigationProvider>
          <TopProgressBar />
          {/* useSearchParams() inside HeaderBar requires a Suspense boundary,
              or Next.js opts the whole route out of static rendering. */}
          <Suspense fallback={null}>
            <HeaderBar repos={repos} />
          </Suspense>
          <ContentTransition>{children}</ContentTransition>
        </RepoNavigationProvider>
      </body>
    </html>
  );
}
