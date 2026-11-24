/**
 * src/lib/shiftLogic.js
 * Pure helpers for the Shifts admin tab — no React, fully testable.
 */

const HOURS_IN_DAY = 24;

/**
 * Given a shift and a reference date string "YYYY-MM-DD",
 * compute the left % and width % for a 24-hour horizontal timeline bar.
 *
 * Shifts crossing midnight are clipped to [day_start, day_end].
 * Returns null if the shift has no overlap with the given day.
 *
 * @param {{ start_time: string, end_time: string }} shift  ISO datetime strings
 * @param {string} dateStr  "YYYY-MM-DD" reference day (local time)
 * @returns {{ leftPct: number, widthPct: number } | null}
 */
export function shiftPosition(shift, dateStr) {
  const dayStart = new Date(`${dateStr}T00:00:00`);
  const dayEnd   = new Date(`${dateStr}T24:00:00`); // = next day 00:00

  const shiftStart = new Date(shift.start_time);
  const shiftEnd   = new Date(shift.end_time);

  // No overlap with the day
  if (shiftEnd <= dayStart || shiftStart >= dayEnd) return null;

  // Clip to day bounds
  const clippedStart = shiftStart < dayStart ? dayStart : shiftStart;
  const clippedEnd   = shiftEnd   > dayEnd   ? dayEnd   : shiftEnd;

  const totalMs    = dayEnd.getTime() - dayStart.getTime();
  const startMs    = clippedStart.getTime() - dayStart.getTime();
  const durationMs = clippedEnd.getTime() - clippedStart.getTime();

  const leftPct  = (startMs / totalMs) * 100;
  const widthPct = (durationMs / totalMs) * 100;

  return { leftPct, widthPct };
}

/**
 * Format an ISO datetime string as "HH:MM" in local time.
 * @param {string} isoString
 * @returns {string}
 */
export function formatShiftTime(isoString) {
  if (!isoString) return '—';
  const d = new Date(isoString);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
}
