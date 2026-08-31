import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "var(--surface-1)",
        plane: "var(--page-plane)",
        ink: {
          primary: "var(--text-primary)",
          secondary: "var(--text-secondary)",
          muted: "var(--text-muted)",
        },
        grid: "var(--gridline)",
        baseline: "var(--baseline)",
        border: "var(--border-ring)",
        series: {
          1: "var(--series-1)",
        },
      },
    },
  },
  plugins: [],
};

export default config;
