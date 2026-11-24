/**
 * Pure dashboard logic — no React, fully testable.
 * Covers: escalation detection, wait-time formatting, bed grouping,
 * queue filtering, and the "critical wait too long" rule.
 */

// ---------------------------------------------------------------------------
// Escalation detection
// ---------------------------------------------------------------------------

/**
 * Given a previous level map {patient_id → level} and a fresh patient list,
 * returns an array of patient ids whose urgency_level got MORE severe
 * (i.e. the new level number is LOWER than the previous one).
 *
 * New patients (not in prevMap) are NOT considered escalated.
 *
 * @param {Record<number, number>} prevMap   patient_id → previous urgency_level
 * @param {Array<{id: number, urgency_level: number}>} nextList
 * @returns {number[]} ids of escalated patients
 */
export function detectEscalations(prevMap, nextList) {
  const escalated = [];
  for (const patient of nextList) {
    const prev = prevMap[patient.id];
    if (prev == null) continue; // new patient — not an escalation
    if (patient.urgency_level != null && patient.urgency_level < prev) {
      escalated.push(patient.id);
    }
  }
  return escalated;
}

/**
 * Build a level map {patient_id → urgency_level} from a patient list.
 * Convenience helper to pass as prevMap to detectEscalations on the next tick.
 *
 * @param {Array<{id: number, urgency_level: number}>} list
 * @returns {Record<number, number>}
 */
export function buildLevelMap(list) {
  const map = {};
  for (const p of list) {
    if (p.urgency_level != null) map[p.id] = p.urgency_level;
  }
  return map;
}

// ---------------------------------------------------------------------------
// Wait-time formatting
// ---------------------------------------------------------------------------

/**
 * Format a wait time in fractional minutes to a human string.
 * < 1 min → "< 1 min"
 * 1–59   → "X min"
 * 60+    → "Xh Ym"
 *
 * @param {number} minutes
 * @returns {string}
 */
export function formatWaitTime(minutes) {
  if (minutes == null || isNaN(minutes)) return '—';
  if (minutes < 1) return '< 1 min';
  const mins = Math.round(minutes);
  if (mins < 60) return `${mins} min`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m === 0 ? `${h}h` : `${h}h ${m}m`;
}

// ---------------------------------------------------------------------------
// Critical wait too long
// ---------------------------------------------------------------------------

/**
 * Returns true if a queue patient should trigger the "critical wait too long"
 * warning: urgency_level 1 or 2 AND waiting longer than 5 minutes.
 *
 * @param {{ urgency_level: number, wait_minutes: number }} patient
 * @returns {boolean}
 */
export function isCriticalWaitTooLong(patient) {
  return (
    patient.urgency_level != null &&
    patient.urgency_level <= 2 &&
    patient.wait_minutes > 5
  );
}

// ---------------------------------------------------------------------------
// Bed grouping
// ---------------------------------------------------------------------------

/**
 * Group an array of beds by their ward field.
 * Returns a plain object { ward: bed[] }.
 *
 * @param {Array<{id: string, ward: string, status: string, has_ventilator: boolean}>} beds
 * @returns {Record<string, typeof beds>}
 */
export function groupBedsByWard(beds) {
  const groups = {};
  for (const bed of beds) {
    if (!groups[bed.ward]) groups[bed.ward] = [];
    groups[bed.ward].push(bed);
  }
  return groups;
}

// ---------------------------------------------------------------------------
// Queue filter / search
// ---------------------------------------------------------------------------

/**
 * Filter and search a queue list.
 *
 * @param {Array} queue      - raw queue from the API
 * @param {string} colorFilter - 'ALL' | 'RED' | 'YELLOW' | 'GREEN'
 * @param {string} search    - substring match against patient name (case-insensitive)
 * @returns {Array} filtered queue in original order
 */
export function filterQueue(queue, colorFilter = 'ALL', search = '') {
  let result = queue;

  if (colorFilter && colorFilter !== 'ALL') {
    result = result.filter((p) => p.color === colorFilter);
  }

  const q = search.trim().toLowerCase();
  if (q) {
    result = result.filter((p) => p.name?.toLowerCase().includes(q));
  }

  return result;
}
