/**
 * src/lib/analyticsLogic.js
 * Pure helpers for the Analytics page — no React, fully testable.
 */

// ---------------------------------------------------------------------------
// Minutes formatting
// ---------------------------------------------------------------------------

/**
 * Format a minutes value into a human string.
 *   null / undefined / NaN → "—"
 *   0                      → "0 min"
 *   < 60                   → "X min"
 *   >= 60                  → "1 h 05 min"
 *
 * @param {number|null|undefined} minutes
 * @returns {string}
 */
export function formatMinutes(minutes) {
  if (minutes == null || isNaN(minutes)) return '—';
  const mins = Math.round(minutes);
  if (mins === 0) return '0 min';
  if (mins < 60) return `${mins} min`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m === 0 ? `${h} h` : `${h} h ${String(m).padStart(2, '0')} min`;
}

// ---------------------------------------------------------------------------
// Triage distribution chart data
// ---------------------------------------------------------------------------

/**
 * Triage colour → Tailwind-compatible hex for recharts bars.
 * Must match levelInfo() in urgency.jsx.
 */
const LEVEL_HEX = {
  1: '#dc2626', // red-600
  2: '#f97316', // orange-500
  3: '#facc15', // yellow-400
  4: '#22c55e', // green-500
  5: '#15803d', // green-700
};

/**
 * Convert /analytics/triage-distribution response into recharts bar data.
 * Always returns all 5 levels, even those with count 0.
 * Adds a `fill` property with the hex colour and a pct (0-100).
 *
 * @param {{ distribution: Array<{level, label, color, count}> }} apiData
 * @returns {Array<{level, label, count, fill, pct}>}
 */
export function toDistributionChartData(apiData) {
  const dist = apiData?.distribution ?? [];
  const total = dist.reduce((s, d) => s + (d.count ?? 0), 0);

  // Ensure all 5 levels present
  const byLevel = {};
  for (const d of dist) byLevel[d.level] = d;

  return [1, 2, 3, 4, 5].map((lvl) => {
    const d = byLevel[lvl] ?? { level: lvl, label: `Level ${lvl}`, count: 0 };
    return {
      level: lvl,
      label: d.label,
      count: d.count ?? 0,
      fill: LEVEL_HEX[lvl] ?? '#6b7280',
      pct: total > 0 ? Math.round(((d.count ?? 0) / total) * 100) : 0,
    };
  });
}

// ---------------------------------------------------------------------------
// Wait-by-level chart data
// ---------------------------------------------------------------------------

/**
 * Convert /analytics/wait-by-level response into recharts bar data.
 * Always returns all 5 levels. avg_wait_minutes rounded to 1 decimal.
 *
 * @param {{ wait_by_level: Array<{level, label, avg_wait_minutes, patient_count}> }} apiData
 * @returns {Array<{level, label, avg_wait_minutes, fill, patient_count}>}
 */
export function toWaitByLevelChartData(apiData) {
  const list = apiData?.wait_by_level ?? [];
  const byLevel = {};
  for (const d of list) byLevel[d.level] = d;

  return [1, 2, 3, 4, 5].map((lvl) => {
    const d = byLevel[lvl] ?? { level: lvl, label: `Level ${lvl}`, avg_wait_minutes: 0, patient_count: 0 };
    return {
      level: lvl,
      label: d.label,
      avg_wait_minutes: Math.round((d.avg_wait_minutes ?? 0) * 10) / 10,
      fill: LEVEL_HEX[lvl] ?? '#6b7280',
      patient_count: d.patient_count ?? 0,
    };
  });
}

// ---------------------------------------------------------------------------
// Occupancy chart data
// ---------------------------------------------------------------------------

/**
 * Convert /analytics/occupancy response into an array of stacked-bar entries,
 * one per ward, ordered ICU → EMERGENCY → GENERAL.
 *
 * @param {{ wards: Record<string, {total, available, occupied, cleaning, occupancy_pct}> }} apiData
 * @returns {Array<{ward, available, occupied, cleaning, total, occupancy_pct}>}
 */
export function toOccupancyChartData(apiData) {
  const wards = apiData?.wards ?? {};
  const ORDER = ['ICU', 'EMERGENCY', 'GENERAL'];
  return ORDER
    .filter((w) => wards[w] != null)
    .map((w) => ({
      ward: w,
      available: wards[w].available ?? 0,
      occupied: wards[w].occupied ?? 0,
      cleaning: wards[w].cleaning ?? 0,
      total: wards[w].total ?? 0,
      occupancy_pct: wards[w].occupancy_pct ?? 0,
    }));
}

// ---------------------------------------------------------------------------
// Timeline chart data  
// ---------------------------------------------------------------------------

/**
 * Convert /analytics/timeline response into recharts area/line data.
 * Labels are abbreviated to HH:00 for readability.
 *
 * @param {{ timeline: Array<{hour, arrivals, critical}> }} apiData
 * @returns {Array<{hour, arrivals, critical, label}>}
 */
export function toTimelineChartData(apiData) {
  return (apiData?.timeline ?? []).map((entry) => ({
    hour: entry.hour,
    arrivals: entry.arrivals ?? 0,
    critical: entry.critical ?? 0,
    label: entry.hour?.slice(11, 16) ?? entry.hour, // "HH:00"
  }));
}

// ---------------------------------------------------------------------------
// Pagination offset
// ---------------------------------------------------------------------------

/**
 * Calculate the API offset for 0-based page number and page size.
 * @param {number} page  0-based page index
 * @param {number} size  items per page
 * @returns {number} offset
 */
export function pageOffset(page, size) {
  return page * size;
}
