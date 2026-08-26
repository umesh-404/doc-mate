"use client";

import { cn } from "@/lib/utils";

/**
 * Tiny hand-rolled inline-SVG line chart for a short numeric series (e.g. two
 * HbA1c readings). No chart library — just a polyline + endpoint dots, themed
 * with the app's CSS colour tokens. Purely a visual aid; the exact values and
 * their citations still live in the item text.
 */
export function Sparkline({
  values,
  className,
  width = 96,
  height = 28,
}: {
  values: number[];
  className?: string;
  width?: number;
  height?: number;
}) {
  if (values.length < 2) return null;

  const pad = 3;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const stepX = (width - pad * 2) / (values.length - 1);

  const points = values.map((v, i) => {
    const x = pad + i * stepX;
    // Higher value = higher on the chart (invert y).
    const y = pad + (1 - (v - min) / span) * (height - pad * 2);
    return { x, y };
  });

  const path = points.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
  const last = points[points.length - 1]!;
  // Rising last-vs-first is framed as danger for most labs; falling as neutral.
  const rising = values[values.length - 1]! > values[0]!;

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={cn("overflow-visible", className)}
      role="img"
      aria-label={`Trend: ${values.join(" to ")}`}
    >
      <polyline
        points={path}
        fill="none"
        stroke={rising ? "hsl(var(--danger))" : "hsl(var(--primary))"}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {points.map((p, i) => (
        <circle
          key={i}
          cx={p.x}
          cy={p.y}
          r={i === points.length - 1 ? 2.6 : 1.8}
          fill={
            i === points.length - 1
              ? rising
                ? "hsl(var(--danger))"
                : "hsl(var(--primary))"
              : "hsl(var(--muted))"
          }
        />
      ))}
      <text
        x={last.x + 4}
        y={last.y + 3}
        fontSize="9"
        fill="hsl(var(--muted))"
        className="hidden sm:block"
      >
        {values[values.length - 1]}
      </text>
    </svg>
  );
}

/**
 * Pull a numeric series out of a free-text lab line. The summary contract
 * carries labs as prose (e.g. "HbA1c rose from 7.1 to 8.2"), so we extract the
 * numbers in order. Returns the series only when there are at least two, so a
 * single reading doesn't render a meaningless chart.
 */
export function extractSeries(text: string): number[] {
  const matches = text.match(/-?\d+(?:\.\d+)?/g);
  if (!matches) return [];
  const nums = matches
    .map((m) => Number(m))
    .filter((n) => Number.isFinite(n));
  return nums.length >= 2 ? nums : [];
}
