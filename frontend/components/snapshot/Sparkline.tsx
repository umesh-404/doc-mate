"use client";

import { cn } from "@/lib/utils";

/**
 * Tiny hand-rolled inline-SVG line chart for a short numeric series (e.g. two
 * HbA1c readings). No chart library — a soft area fill, the trend line, muted
 * intermediate dots and an emphasised final reading with its value called out,
 * plus faint first/last baseline hints so the direction reads instantly.
 *
 * Purely a visual aid: the exact values and their citations still live in the
 * item text, and nothing here is interpreted as a clinical finding.
 */
export function Sparkline({
  values,
  className,
  width = 132,
  height = 34,
  label,
}: {
  values: number[];
  className?: string;
  width?: number;
  height?: number;
  /** Accessible description; defaults to reading the series aloud. */
  label?: string;
}) {
  if (values.length < 2) return null;

  const padX = 4;
  const padY = 6;
  // Reserve room on the right for the last-value label.
  const plotW = width - padX * 2 - 30;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const stepX = plotW / (values.length - 1);

  const points = values.map((v, i) => {
    const x = padX + i * stepX;
    // Higher value = higher on the chart (invert y).
    const y = padY + (1 - (v - min) / span) * (height - padY * 2);
    return { x, y };
  });

  const line = points.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
  const first = points[0]!;
  const last = points[points.length - 1]!;
  const lastValue = values[values.length - 1]!;

  // Rising last-vs-first is drawn in danger for most labs; falling in primary.
  const rising = lastValue > values[0]!;
  const stroke = rising ? "hsl(var(--danger))" : "hsl(var(--primary))";
  const areaId = `spark-${rising ? "up" : "down"}`;

  const area = `${line} ${last.x.toFixed(1)},${height - padY / 2} ${first.x.toFixed(
    1,
  )},${height - padY / 2}`;

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={cn("overflow-visible", className)}
      role="img"
      aria-label={label ?? `Trend: ${values.join(" to ")}`}
    >
      <defs>
        <linearGradient id={areaId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.18" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* Baseline axis hint */}
      <line
        x1={padX}
        y1={height - padY / 2}
        x2={padX + plotW}
        y2={height - padY / 2}
        stroke="hsl(var(--border))"
        strokeWidth="1"
      />

      <polygon points={area} fill={`url(#${areaId})`} />

      <polyline
        points={line}
        fill="none"
        stroke={stroke}
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {points.slice(0, -1).map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r={1.7} fill="hsl(var(--muted))" />
      ))}

      {/* Last reading: haloed so it stands out against the line. */}
      <circle
        cx={last.x}
        cy={last.y}
        r={4.5}
        fill="hsl(var(--surface))"
        stroke={stroke}
        strokeWidth="2"
      />

      <text
        x={last.x + 8}
        y={last.y + 3.5}
        fontSize="10"
        fontWeight="700"
        fill={stroke}
      >
        {lastValue}
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
