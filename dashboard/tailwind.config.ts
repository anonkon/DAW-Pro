import type { Config } from "tailwindcss";

// Every value here points at a custom property defined in app/tokens.css.
// Nothing is duplicated: tokens.css is the source of truth, so the plugin
// WebView - which cannot run Tailwind - resolves the same values.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          base: "var(--surface-base)",
          panel: "var(--surface-panel)",
          raised: "var(--surface-raised)",
          hover: "var(--surface-hover)",
        },
        ink: {
          primary: "var(--text-primary)",
          secondary: "var(--text-secondary)",
          muted: "var(--text-muted)",
          onAccent: "var(--text-on-accent)",
        },
        line: {
          subtle: "var(--border-subtle)",
          DEFAULT: "var(--border-default)",
          strong: "var(--border-strong)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          hover: "var(--accent-hover)",
          dim: "var(--accent-dim)",
        },
        viz: {
          project: "var(--viz-project)",
          "project-soft": "var(--viz-project-soft)",
          reference: "var(--viz-reference)",
          "reference-soft": "var(--viz-reference-soft)",
          grid: "var(--viz-grid)",
          axis: "var(--viz-axis)",
        },
        status: {
          critical: "var(--status-critical)",
          "critical-bg": "var(--status-critical-bg)",
          warning: "var(--status-warning)",
          "warning-bg": "var(--status-warning-bg)",
          info: "var(--status-info)",
          "info-bg": "var(--status-info-bg)",
        },
      },
      fontFamily: {
        sans: "var(--font-sans)",
        mono: "var(--font-mono)",
      },
      fontSize: {
        display: "var(--text-display)",
        body: "var(--text-body)",
        small: "var(--text-small)",
        label: "var(--text-label)",
      },
      letterSpacing: {
        label: "var(--tracking-label)",
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        DEFAULT: "var(--radius)",
        lg: "var(--radius-lg)",
      },
      boxShadow: {
        accent: "0 0 0 1px var(--accent-dim), 0 0 24px -6px var(--accent-glow)",
      },
    },
  },
  plugins: [],
};

export default config;
