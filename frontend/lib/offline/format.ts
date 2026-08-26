/**
 * Human-readable staleness. Deliberately coarse — the point is for a doctor to
 * judge at a glance whether a cached record is trustworthy, not to display a
 * clock. Rounded DOWN so a copy never looks fresher than it is.
 */

import type { Dictionary } from "../i18n/dictionaries";

/** Replace `{n}` in a dictionary string. Keeps the templates translator-safe. */
export function fill(template: string, n: number | string): string {
  return template.replace("{n}", String(n));
}

export function formatAgo(fetchedAt: number | null, t: Dictionary): string {
  if (!fetchedAt) return t.offline.neverSynced;
  const seconds = Math.max(0, Math.floor((Date.now() - fetchedAt) / 1000));
  if (seconds < 60) return t.offline.justNow;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return fill(t.offline.minutesAgo, minutes);
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return fill(t.offline.hoursAgo, hours);
  return fill(t.offline.daysAgo, Math.floor(hours / 24));
}
