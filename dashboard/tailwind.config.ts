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
        status: {
          good: "var(--status-good)",
          warning: "var(--status-warning)",
          serious: "var(--status-serious)",
          critical: "var(--status-critical)",
        },
      },
      boxShadow: {
        card: "var(--shadow-md)",
        lifted: "var(--shadow-lifted)",
      },
      keyframes: {
        "progress-sweep": {
          "0%": { transform: "translateX(-100%) scaleX(0.4)" },
          "60%": { transform: "translateX(30%) scaleX(0.6)" },
          "100%": { transform: "translateX(100%) scaleX(0.4)" },
        },
      },
      animation: {
        "progress-sweep": "progress-sweep 1.1s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
