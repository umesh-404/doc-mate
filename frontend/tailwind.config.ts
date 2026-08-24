import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Clinical design tokens (mapped to CSS variables in globals.css)
        bg: "hsl(var(--bg) / <alpha-value>)",
        surface: "hsl(var(--surface) / <alpha-value>)",
        "surface-muted": "hsl(var(--surface-muted) / <alpha-value>)",
        border: "hsl(var(--border) / <alpha-value>)",
        foreground: "hsl(var(--foreground) / <alpha-value>)",
        muted: "hsl(var(--muted) / <alpha-value>)",
        primary: "hsl(var(--primary) / <alpha-value>)",
        "primary-foreground": "hsl(var(--primary-foreground) / <alpha-value>)",
        accent: "hsl(var(--accent) / <alpha-value>)",
        danger: "hsl(var(--danger) / <alpha-value>)",
        "danger-surface": "hsl(var(--danger-surface) / <alpha-value>)",
        warning: "hsl(var(--warning) / <alpha-value>)",
        "warning-surface": "hsl(var(--warning-surface) / <alpha-value>)",
        success: "hsl(var(--success) / <alpha-value>)",
        "success-surface": "hsl(var(--success-surface) / <alpha-value>)",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      },
      borderRadius: {
        lg: "0.75rem",
        md: "0.5rem",
        sm: "0.375rem",
      },
      boxShadow: {
        card: "0 1px 2px 0 hsl(215 25% 27% / 0.04), 0 1px 3px 0 hsl(215 25% 27% / 0.06)",
        "card-lg": "0 4px 12px -2px hsl(215 25% 27% / 0.08), 0 2px 6px -2px hsl(215 25% 27% / 0.06)",
      },
    },
  },
  plugins: [],
};

export default config;
