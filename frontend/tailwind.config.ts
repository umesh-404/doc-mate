import type { Config } from "tailwindcss";

/**
 * Doc-mate clinical design tokens.
 *
 * Every colour maps to an HSL-channel CSS variable declared in app/globals.css,
 * so the same class names resolve correctly in light and dark. Dark mode uses
 * the `class` strategy — lib/theme.tsx toggles `.dark` on <html>.
 */
const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "hsl(var(--bg) / <alpha-value>)",
        "bg-accent": "hsl(var(--bg-accent) / <alpha-value>)",
        surface: "hsl(var(--surface) / <alpha-value>)",
        "surface-muted": "hsl(var(--surface-muted) / <alpha-value>)",
        "surface-raised": "hsl(var(--surface-raised) / <alpha-value>)",
        border: "hsl(var(--border) / <alpha-value>)",
        "border-strong": "hsl(var(--border-strong) / <alpha-value>)",
        "control-border": "hsl(var(--control-border) / <alpha-value>)",
        foreground: "hsl(var(--foreground) / <alpha-value>)",
        "foreground-subtle": "hsl(var(--foreground-subtle) / <alpha-value>)",
        muted: "hsl(var(--muted) / <alpha-value>)",
        ring: "hsl(var(--ring) / <alpha-value>)",

        primary: "hsl(var(--primary) / <alpha-value>)",
        "primary-hover": "hsl(var(--primary-hover) / <alpha-value>)",
        "primary-foreground": "hsl(var(--primary-foreground) / <alpha-value>)",
        accent: "hsl(var(--accent) / <alpha-value>)",

        danger: "hsl(var(--danger) / <alpha-value>)",
        "danger-strong": "hsl(var(--danger-strong) / <alpha-value>)",
        "danger-surface": "hsl(var(--danger-surface) / <alpha-value>)",
        "danger-foreground": "hsl(var(--danger-foreground) / <alpha-value>)",
        warning: "hsl(var(--warning) / <alpha-value>)",
        "warning-strong": "hsl(var(--warning-strong) / <alpha-value>)",
        "warning-surface": "hsl(var(--warning-surface) / <alpha-value>)",
        success: "hsl(var(--success) / <alpha-value>)",
        "success-surface": "hsl(var(--success-surface) / <alpha-value>)",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      /* A deliberate clinical type scale — tight display sizes, roomy body. */
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.01em" }],
        xs: ["0.75rem", { lineHeight: "1.1rem" }],
        sm: ["0.8125rem", { lineHeight: "1.25rem" }],
        base: ["0.875rem", { lineHeight: "1.4rem" }],
        md: ["0.9375rem", { lineHeight: "1.5rem" }],
        lg: ["1.0625rem", { lineHeight: "1.6rem" }],
        xl: ["1.25rem", { lineHeight: "1.75rem", letterSpacing: "-0.011em" }],
        "2xl": ["1.5rem", { lineHeight: "1.95rem", letterSpacing: "-0.018em" }],
        "3xl": ["1.875rem", { lineHeight: "2.25rem", letterSpacing: "-0.022em" }],
        "4xl": ["2.25rem", { lineHeight: "2.6rem", letterSpacing: "-0.026em" }],
      },
      spacing: {
        4.5: "1.125rem",
        13: "3.25rem",
        18: "4.5rem",
      },
      borderRadius: {
        xl: "1rem",
        lg: "0.75rem",
        md: "0.5rem",
        sm: "0.375rem",
      },
      boxShadow: {
        card: "0 1px 2px 0 hsl(var(--shadow-color) / calc(0.05 * var(--shadow-strength))), 0 1px 3px -1px hsl(var(--shadow-color) / calc(0.07 * var(--shadow-strength)))",
        "card-lg":
          "0 4px 12px -3px hsl(var(--shadow-color) / calc(0.09 * var(--shadow-strength))), 0 2px 6px -2px hsl(var(--shadow-color) / calc(0.07 * var(--shadow-strength)))",
        float:
          "0 12px 32px -8px hsl(var(--shadow-color) / calc(0.18 * var(--shadow-strength))), 0 4px 10px -4px hsl(var(--shadow-color) / calc(0.10 * var(--shadow-strength)))",
        "inner-line": "inset 0 -1px 0 0 hsl(var(--border))",
      },
      keyframes: {
        "rise-in": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "none" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "expand-down": {
          from: { opacity: "0", transform: "translateY(-4px)" },
          to: { opacity: "1", transform: "none" },
        },
        /* Critical-alert severity rail only. */
        "rail-pulse": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.4" },
        },
      },
      animation: {
        "rise-in": "rise-in 0.4s cubic-bezier(0.22, 1, 0.36, 1) both",
        "fade-in": "fade-in 0.3s ease-out both",
        "expand-down": "expand-down 0.22s cubic-bezier(0.22, 1, 0.36, 1) both",
        "rail-pulse": "rail-pulse 2.6s ease-in-out infinite",
      },
      transitionTimingFunction: {
        clinical: "cubic-bezier(0.22, 1, 0.36, 1)",
      },
    },
  },
  plugins: [],
};

export default config;
